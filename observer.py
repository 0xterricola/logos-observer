#!/usr/bin/env python3

import argparse
import fcntl
import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROTOCOL = "logos-observer-v1"

LISTEN_HOST = "192.168.1.160"
LISTEN_PORT = 8081
PUBLIC_BASE = f"http://{LISTEN_HOST}:{LISTEN_PORT}"

UPSTREAM = "http://127.0.0.1:8080"

STATE_DIR = Path("/var/lib/logos-observer")
DEVICES_FILE = STATE_DIR / "devices.json"
DEVICE_LOCK_FILE = STATE_DIR / "devices.lock"

PAIR_TTL_SECONDS = 5 * 60
REQUEST_SKEW_SECONDS = 60
NONCE_TTL_SECONDS = 5 * 60

MAX_RESPONSE = 1024 * 1024
UPSTREAM_TIMEOUT = 5

HKDF_SALT = b"logos-observer-v1"
REQUEST_AUTH_INFO = b"request-auth"
RESPONSE_AEAD_INFO = b"response-aead"

PAIR_REQUEST_AUTH_INFO = b"pairing-request-auth"
PAIR_REQUEST_AEAD_INFO = b"pairing-request-aead"
PAIR_RESPONSE_AEAD_INFO = b"pairing-response-aead"
RESPONSE_ALG = "A256GCM"

class ProcessFileLock:
    def __init__(self, path):
        self.path = path
        self.thread_lock = threading.RLock()
        self.local = threading.local()

    def __enter__(self):
        self.thread_lock.acquire()

        depth = getattr(
            self.local,
            "depth",
            0,
        )

        if depth == 0:
            handle = open(
                self.path,
                "a+",
            )

            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_EX,
            )

            self.local.handle = handle

        self.local.depth = depth + 1

        return self

    def __exit__(
        self,
        exc_type,
        exc_value,
        traceback,
    ):
        depth = self.local.depth - 1

        if depth == 0:
            handle = self.local.handle

            fcntl.flock(
                handle.fileno(),
                fcntl.LOCK_UN,
            )

            handle.close()

            del self.local.handle

        self.local.depth = depth

        self.thread_lock.release()


DB_LOCK = ProcessFileLock(
    DEVICE_LOCK_FILE
)

NONCE_DB = STATE_DIR / "nonces.sqlite3"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def b64url(data):
    return (
        base64.urlsafe_b64encode(data)
        .decode("ascii")
        .rstrip("=")
    )


def b64url_decode(value):
    try:
        padding = (
            "="
            * ((4 - len(value) % 4) % 4)
        )

        return base64.urlsafe_b64decode(
            value + padding
        )

    except Exception as exc:
        raise ValueError(
            "invalid base64url"
        ) from exc


def read_db_unlocked():
    return json.loads(DEVICES_FILE.read_text())


def write_db_unlocked(db):
    fd, temp_name = tempfile.mkstemp(
        prefix="devices.",
        suffix=".tmp",
        dir=STATE_DIR,
        text=True,
    )

    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(
                db,
                handle,
                separators=(",", ":"),
                sort_keys=True,
            )
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.chmod(temp_name, 0o600)
        os.replace(temp_name, DEVICES_FILE)

    finally:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass


def load_db():
    with DB_LOCK:
        return read_db_unlocked()


def secret_bytes(device):
    raw = device["secret"]
    padding = "=" * ((4 - len(raw) % 4) % 4)

    return base64.urlsafe_b64decode(
        raw + padding
    )


def derive_key(
    root_secret,
    info,
):
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=HKDF_SALT,
        info=info,
    ).derive(root_secret)


def request_auth_key(device):
    return derive_key(
        secret_bytes(device),
        REQUEST_AUTH_INFO,
    )


def response_aead_key(device):
    return derive_key(
        secret_bytes(device),
        RESPONSE_AEAD_INFO,
    )


def canonical_request(
    device_id,
    method,
    path,
    timestamp,
    nonce,
    body_hash,
):
    fields = [
        PROTOCOL,
        device_id,
        method.upper(),
        path,
        timestamp,
        nonce,
        body_hash,
    ]

    return chr(10).join(fields).encode("utf-8")


def canonical_response_aad(
    device_id,
    method,
    path,
    request_nonce,
    status,
    response_time,
):
    fields = [
        PROTOCOL,
        RESPONSE_ALG,
        device_id,
        method.upper(),
        path,
        request_nonce,
        str(status),
        response_time,
    ]

    return chr(10).join(
        fields
    ).encode("utf-8")


def upstream_json(path):
    request = urllib.request.Request(
        UPSTREAM + path,
        method="GET",
        headers={
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=UPSTREAM_TIMEOUT,
    ) as response:

        payload = response.read(
            MAX_RESPONSE + 1
        )

        if len(payload) > MAX_RESPONSE:
            raise ValueError(
                "upstream response too large"
            )

        return json.loads(payload)


def consume_nonce(
    device_id,
    nonce,
    now,
):
    cutoff = now - NONCE_TTL_SECONDS

    with sqlite3.connect(
        NONCE_DB,
        timeout=5,
    ) as db:
        db.execute(
            "PRAGMA busy_timeout = 5000"
        )

        db.execute(
            """
            CREATE TABLE IF NOT EXISTS seen_nonces (
                device_id TEXT NOT NULL,
                nonce TEXT NOT NULL,
                seen_at INTEGER NOT NULL,
                PRIMARY KEY (device_id, nonce)
            )
            """
        )

        db.execute(
            "DELETE FROM seen_nonces "
            "WHERE seen_at < ?",
            (cutoff,),
        )

        try:
            db.execute(
                """
                INSERT INTO seen_nonces (
                    device_id,
                    nonce,
                    seen_at
                )
                VALUES (?, ?, ?)
                """,
                (
                    device_id,
                    nonce,
                    now,
                ),
            )

        except sqlite3.IntegrityError:
            return False

    return True

def validate_common_headers(handler):
    version = handler.headers.get(
        "X-Observer-Version",
        "",
    )

    device_id = handler.headers.get(
        "X-Observer-Device",
        "",
    )

    timestamp = handler.headers.get(
        "X-Observer-Time",
        "",
    )

    nonce = handler.headers.get(
        "X-Observer-Nonce",
        "",
    )

    signature = handler.headers.get(
        "X-Observer-Signature",
        "",
    ).lower()

    if not all([
        version,
        device_id,
        timestamp,
        nonce,
        signature,
    ]):
        return None, "missing_auth_headers"

    if version != "1":
        return None, "unsupported_version"

    try:
        request_time = int(timestamp)

    except ValueError:
        return None, "invalid_timestamp"

    now = int(time.time())

    if abs(
        now - request_time
    ) > REQUEST_SKEW_SECONDS:
        return None, "stale_request"

    try:
        nonce_bytes = bytes.fromhex(
            nonce
        )

    except ValueError:
        return None, "invalid_nonce"

    # Protocol v1 nonces are exactly 16 random
    # bytes encoded as 32 hex characters.
    if len(nonce_bytes) != 16:
        return None, "invalid_nonce"

    return {
        "device_id": device_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "signature": signature,
        "now": now,
    }, None


def canonical_pairing_request_aad(
    device_id,
    timestamp,
    request_nonce,
):
    fields = [
        PROTOCOL,
        RESPONSE_ALG,
        "pairing-request",
        device_id,
        "POST",
        "/v1/pair/activate",
        timestamp,
        request_nonce,
    ]

    return chr(10).join(
        fields
    ).encode("utf-8")


def authorize(
    handler,
    body=b"",
):
    common, error = (
        validate_common_headers(
            handler
        )
    )

    if error:
        return False, error, None

    device_id = common[
        "device_id"
    ]

    db = load_db()

    device = db.get(
        "devices",
        {},
    ).get(device_id)

    if (
        not device
        or device.get("revoked")
    ):
        return False, "unknown_device", None

    # A pending QR credential is NOT a normal
    # API credential.
    if device.get("pending"):
        return False, "pairing_required", None

    if "secret" not in device:
        return False, "device_not_ready", None

    body_hash = hashlib.sha256(
        body
    ).hexdigest()

    canonical = canonical_request(
        device_id,
        handler.command,
        handler.path,
        common["timestamp"],
        common["nonce"],
        body_hash,
    )

    expected = hmac.new(
        request_auth_key(device),
        canonical,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        common["signature"],
        expected,
    ):
        return False, "invalid_signature", None

    if not consume_nonce(
        device_id,
        common["nonce"],
        common["now"],
    ):
        return False, "replayed_request", None

    return True, None, {
        "device_id": device_id,
        "request_nonce":
            common["nonce"],
        "response_key":
            response_aead_key(device),
    }


def authorize_pairing(
    handler,
    body,
):
    common, error = (
        validate_common_headers(
            handler
        )
    )

    if error:
        return False, error, None

    device_id = common[
        "device_id"
    ]

    db = load_db()

    device = db.get(
        "devices",
        {},
    ).get(device_id)

    if (
        not device
        or device.get("revoked")
    ):
        return False, "unknown_device", None

    if not device.get("pending"):
        return (
            False,
            "pairing_not_pending",
            None,
        )

    if common["now"] > device.get(
        "pendingUntil",
        0,
    ):
        return (
            False,
            "pairing_expired",
            None,
        )

    bootstrap_text = device.get(
        "bootstrapSecret"
    )

    if not bootstrap_text:
        return (
            False,
            "pairing_not_ready",
            None,
        )

    bootstrap = b64url_decode(
        bootstrap_text
    )

    if len(bootstrap) != 32:
        return (
            False,
            "pairing_not_ready",
            None,
        )

    body_hash = hashlib.sha256(
        body
    ).hexdigest()

    canonical = canonical_request(
        device_id,
        handler.command,
        handler.path,
        common["timestamp"],
        common["nonce"],
        body_hash,
    )

    pair_auth_key = derive_key(
        bootstrap,
        PAIR_REQUEST_AUTH_INFO,
    )

    expected = hmac.new(
        pair_auth_key,
        canonical,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(
        common["signature"],
        expected,
    ):
        return False, "invalid_signature", None

    if not consume_nonce(
        device_id,
        common["nonce"],
        common["now"],
    ):
        return False, "replayed_request", None

    return True, None, {
        "device_id": device_id,
        "timestamp":
            common["timestamp"],
        "request_nonce":
            common["nonce"],
        "request_key": derive_key(
            bootstrap,
            PAIR_REQUEST_AEAD_INFO,
        ),
        "response_key": derive_key(
            bootstrap,
            PAIR_RESPONSE_AEAD_INFO,
        ),
        "bootstrap_text":
            bootstrap_text,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "LogosObserver/1"

    def log_message(
        self,
        fmt,
        *args,
    ):
        logging.info(
            "%s %s",
            self.client_address[0],
            fmt % args,
        )

    def send_json(
        self,
        status,
        obj,
        auth_context=None,
    ):
        plaintext = json.dumps(
            obj,
            separators=(",", ":"),
        ).encode("utf-8")

        response_time = None

        if auth_context is None:
            payload = plaintext

        else:
            response_time = str(
                int(time.time())
            )

            aead_nonce = secrets.token_bytes(
                12
            )

            aad = canonical_response_aad(
                auth_context["device_id"],
                self.command,
                self.path,
                auth_context[
                    "request_nonce"
                ],
                status,
                response_time,
            )

            ciphertext = AESGCM(
                auth_context["response_key"]
            ).encrypt(
                aead_nonce,
                plaintext,
                aad,
            )

            envelope = {
                "v": 1,
                "alg": RESPONSE_ALG,
                "nonce": b64url(
                    aead_nonce
                ),
                "ciphertext": b64url(
                    ciphertext
                ),
            }

            payload = json.dumps(
                envelope,
                separators=(",", ":"),
            ).encode("utf-8")

        self.send_response(status)

        self.send_header(
            "Content-Type",
            "application/json",
        )

        self.send_header(
            "Content-Length",
            str(len(payload)),
        )

        self.send_header(
            "Cache-Control",
            "no-store",
        )

        self.send_header(
            "X-Content-Type-Options",
            "nosniff",
        )

        if auth_context is not None:
            self.send_header(
                "X-Observer-Version",
                "1",
            )

            self.send_header(
                "X-Observer-Encryption",
                RESPONSE_ALG,
            )

            self.send_header(
                "X-Observer-Response-Time",
                response_time,
            )

            self.send_header(
                "X-Observer-Request-Nonce",
                auth_context[
                    "request_nonce"
                ],
            )

        self.end_headers()

        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            self.send_json(
                200,
                {
                    "ok": True,
                    "service": "logos-observer",
                    "protocol": PROTOCOL,
                },
            )
            return

        if self.path != "/v1/status":
            self.send_json(
                404,
                {
                    "ok": False,
                    "error": "not_found",
                },
            )
            return

        ok, error, auth_context = authorize(self)

        if not ok:
            self.send_json(
                401,
                {
                    "ok": False,
                    "error": error,
                },
            )
            return

        try:
            consensus = upstream_json(
                "/cryptarchia/info"
            )

            network = upstream_json(
                "/network/info"
            )

            info = consensus.get(
                "cryptarchia_info",
                {},
            )

            peers = network.get(
                "connected_peers",
                [],
            )

            self.send_json(
                200,
                {
                    "version": 1,
                    "node": {
                        "state":
                            info.get("state"),
                        "phase":
                            consensus.get("phase"),
                        "height":
                            info.get("height"),
                        "slot":
                            info.get("slot"),
                        "libSlot":
                            info.get("lib_slot"),
                    },
                    "network": {
                        "connectedPeers":
                            len(peers)
                            if isinstance(
                                peers,
                                list,
                            )
                            else None,
                        "discoveredPeers":
                            network.get(
                                "n_discovered_peers"
                            ),
                    },
                },
                auth_context=auth_context,
            )

        except (
            urllib.error.URLError,
            urllib.error.HTTPError,
            json.JSONDecodeError,
            ValueError,
        ) as exc:

            logging.error(
                "upstream failure: %s",
                type(exc).__name__,
            )

            self.send_json(
                502,
                {
                    "ok": False,
                    "error": "upstream_failure",
                },
                auth_context=auth_context,
            )

    def do_POST(self):
        if self.path != "/v1/pair/activate":
            self.send_json(
                405,
                {
                    "ok": False,
                    "error":
                        "method_not_allowed",
                },
            )
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

        except ValueError:
            self.send_json(
                400,
                {
                    "ok": False,
                    "error":
                        "invalid_length",
                },
            )
            return

        if (
            length <= 0
            or length > 65536
        ):
            self.send_json(
                400,
                {
                    "ok": False,
                    "error":
                        "invalid_request_size",
                },
            )
            return

        body = self.rfile.read(
            length
        )

        (
            ok,
            error,
            pair_context,
        ) = authorize_pairing(
            self,
            body,
        )

        if not ok:
            self.send_json(
                401,
                {
                    "ok": False,
                    "error": error,
                },
            )
            return

        try:
            envelope = json.loads(
                body
            )

            if (
                envelope.get("v") != 1
                or envelope.get("alg")
                != RESPONSE_ALG
            ):
                raise ValueError(
                    "invalid envelope"
                )

            aead_nonce = b64url_decode(
                envelope["nonce"]
            )

            ciphertext = b64url_decode(
                envelope["ciphertext"]
            )

            if len(aead_nonce) != 12:
                raise ValueError(
                    "invalid AEAD nonce"
                )

            aad = (
                canonical_pairing_request_aad(
                    pair_context[
                        "device_id"
                    ],
                    pair_context[
                        "timestamp"
                    ],
                    pair_context[
                        "request_nonce"
                    ],
                )
            )

            plaintext = AESGCM(
                pair_context[
                    "request_key"
                ]
            ).decrypt(
                aead_nonce,
                ciphertext,
                aad,
            )

            activation = json.loads(
                plaintext
            )

            root_text = activation.get(
                "rootSecret",
                "",
            )

            root_secret = (
                b64url_decode(
                    root_text
                )
            )

            if len(root_secret) != 32:
                raise ValueError(
                    "root secret must "
                    "be 32 bytes"
                )

        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidTag,
        ):
            self.send_json(
                400,
                {
                    "ok": False,
                    "error":
                        "invalid_pairing_payload",
                },
                auth_context=
                    pair_context,
            )
            return

        state_changed = False

        with DB_LOCK:
            db = read_db_unlocked()

            device = db.get(
                "devices",
                {},
            ).get(
                pair_context[
                    "device_id"
                ]
            )

            if (
                not device
                or device.get("revoked")
                or not device.get(
                    "pending"
                )
                or device.get(
                    "bootstrapSecret"
                )
                != pair_context[
                    "bootstrap_text"
                ]
            ):
                state_changed = True

            else:
                # The phone generated this permanent
                # root secret. The QR bootstrap is
                # destroyed immediately.
                device["secret"] = (
                    root_text
                )

                device["pending"] = False

                device["pairedAt"] = int(
                    time.time()
                )

                device.pop(
                    "bootstrapSecret",
                    None,
                )

                device.pop(
                    "pendingUntil",
                    None,
                )

                write_db_unlocked(
                    db
                )

        if state_changed:
            self.send_json(
                409,
                {
                    "ok": False,
                    "error":
                        "pairing_state_changed",
                },
                auth_context=
                    pair_context,
            )
            return

        logging.info(
            "paired device=%s",
            pair_context[
                "device_id"
            ],
        )

        self.send_json(
            200,
            {
                "version": 1,
                "status": "paired",
                "deviceId":
                    pair_context[
                        "device_id"
                    ],
            },
            auth_context=
                pair_context,
        )


    def method_not_allowed(self):
        self.send_json(
            405,
            {
                "ok": False,
                "error": "method_not_allowed",
            },
        )

    do_PUT = method_not_allowed
    do_PATCH = method_not_allowed
    do_DELETE = method_not_allowed


def pair_device(name):
    now = int(time.time())

    device_id = (
        "dev_"
        + secrets.token_hex(8)
    )

    bootstrap = b64url(
        secrets.token_bytes(32)
    )

    with DB_LOCK:
        db = read_db_unlocked()

        db.setdefault(
            "devices",
            {},
        )[device_id] = {
            "name": name,
            "bootstrapSecret":
                bootstrap,
            "createdAt": now,
            "pending": True,
            "pendingUntil":
                now + PAIR_TTL_SECONDS,
            "revoked": False,
        }

        write_db_unlocked(db)

    payload = {
        "protocol": PROTOCOL,
        "version": 1,
        "baseURL": PUBLIC_BASE,
        "activationPath":
            "/v1/pair/activate",
        "deviceId": device_id,
        "bootstrapSecret":
            bootstrap,
        "expiresAt":
            now + PAIR_TTL_SECONDS,
    }

    encoded = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    )

    print()
    print(
        f"Pairing device: {name}"
    )

    print(
        f"Device ID: {device_id}"
    )

    print(
        "QR bootstrap expires "
        "in 5 minutes."
    )

    print(
        "The bootstrap secret is "
        "destroyed after activation."
    )

    print(
        "Do NOT screenshot or "
        "share this QR."
    )

    print()

    subprocess.run(
        [
            "qrencode",
            "-t",
            "ANSIUTF8",
            encoded,
        ],
        check=True,
    )


def list_devices():
    db = load_db()

    devices = db.get(
        "devices",
        {},
    )

    if not devices:
        print("No devices.")
        return

    now = int(time.time())

    print(
        f"{'DEVICE ID':<21} "
        f"{'STATE':<10} "
        "NAME"
    )

    for device_id, device in sorted(
        devices.items()
    ):
        if device.get("revoked"):
            state = "revoked"

        elif device.get("pending"):
            if now > device.get(
                "pendingUntil",
                0,
            ):
                state = "expired"
            else:
                state = "pending"

        else:
            state = "active"

        print(
            f"{device_id:<21} "
            f"{state:<10} "
            f"{device.get('name', '')}"
        )


def revoke_device(device_id):
    with DB_LOCK:
        db = read_db_unlocked()

        device = db.get(
            "devices",
            {},
        ).get(device_id)

        if not device:
            raise SystemExit(
                f"unknown device: {device_id}"
            )

        device["revoked"] = True
        device["revokedAt"] = int(
            time.time()
        )

        device.pop(
            "bootstrapSecret",
            None,
        )

        write_db_unlocked(db)

    print(
        f"revoked {device_id}"
    )


def serve():
    logging.info(
        "listening on %s:%d upstream=%s",
        LISTEN_HOST,
        LISTEN_PORT,
        UPSTREAM,
    )

    ThreadingHTTPServer(
        (
            LISTEN_HOST,
            LISTEN_PORT,
        ),
        Handler,
    ).serve_forever()


def main():
    parser = argparse.ArgumentParser(
        description="Logos Observer v1",
    )

    sub = parser.add_subparsers(
        dest="command",
        required=True,
    )

    sub.add_parser("serve")

    pair = sub.add_parser("pair")

    pair.add_argument(
        "--name",
        default="iPhone",
        help="friendly device name",
    )

    sub.add_parser("devices")

    revoke = sub.add_parser("revoke")

    revoke.add_argument(
        "device_id"
    )

    args = parser.parse_args()

    if args.command == "serve":
        serve()

    elif args.command == "pair":
        pair_device(args.name)

    elif args.command == "devices":
        list_devices()

    elif args.command == "revoke":
        revoke_device(
            args.device_id
        )


if __name__ == "__main__":
    main()
