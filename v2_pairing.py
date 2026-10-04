#!/usr/bin/env python3

import contextlib
import fcntl
import hashlib
import hmac
import json
import os
import secrets
import tempfile
import threading
import time
from pathlib import Path
from urllib.parse import quote, urlencode

from v2_crypto import b64url_encode


PAIR_TTL_SECONDS = 5 * 60
PAIR_MAX_FAILURES = 5

V2_READ_SCOPES = (
    "node.status.read",
    "network.status.read",
    "mining.status.read",
    "rewards.status.read",
)

V2_RESERVED_SCOPES = (
    "blend.status.read",
)


class PairingError(Exception):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def build_pairing_qr(
    *,
    expires_at,
    host,
    pin,
    bootstrap_secret,
    display_name,
    scopes,
    bonjour=None,
):
    params = [
        ("v", "2"),
        ("exp", str(expires_at)),
        ("h", host),
    ]

    if bonjour:
        params.append(
            ("b", bonjour)
        )

    params.extend(
        [
            ("pin", pin),
            ("s", bootstrap_secret),
            ("n", display_name),
            ("sc", ",".join(scopes)),
        ]
    )

    query = urlencode(
        params,
        quote_via=quote,
        safe=":/,._-",
    )

    return (
        "logos-observer://pair?"
        + query
    )


class PairingStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.state_file = (
            self.state_dir
            / "v2-pairing.json"
        )

        self.lock = threading.RLock()
        self.lock_file = (
            self.state_dir
            / "v2-pairing.lock"
        )

        # Initialization must use the same process-wide lock as
        # later read/modify/write operations. The pairing CLI and
        # HTTPS server are separate processes and may start at the
        # same time.
        with self._locked():
            if not self.state_file.exists():
                self._write(
                    {
                        "pending": None,
                        "devices": {},
                    }
                )

    @contextlib.contextmanager
    def _locked(self):
        """Serialize pairing state access across threads and processes."""
        with self.lock:
            fd = os.open(
                self.lock_file,
                os.O_CREAT | os.O_RDWR,
                0o600,
            )

            try:
                # Preserve the credential-state security boundary even
                # if an existing lock file has broader permissions.
                os.fchmod(
                    fd,
                    0o600,
                )

                fcntl.flock(
                    fd,
                    fcntl.LOCK_EX,
                )

                yield

            finally:
                try:
                    fcntl.flock(
                        fd,
                        fcntl.LOCK_UN,
                    )
                finally:
                    os.close(fd)

    def _read(self):
        if not self.state_file.exists():
            return {
                "pending": None,
                "devices": {},
            }

        return json.loads(
            self.state_file.read_text()
        )

    def _write(self, state):
        self.state_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        fd, temp_name = tempfile.mkstemp(
            prefix="v2-pairing.",
            dir=self.state_dir,
        )

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8",
            ) as f:
                json.dump(
                    state,
                    f,
                    indent=2,
                    sort_keys=True,
                )
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())

            os.chmod(
                temp_name,
                0o600,
            )

            os.replace(
                temp_name,
                self.state_file,
            )

            os.chmod(
                self.state_file,
                0o600,
            )
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)

    @staticmethod
    def _secret_hash(secret):
        return hashlib.sha256(
            secret.encode("ascii")
        ).hexdigest()

    def create_offer(
        self,
        *,
        host,
        pin,
        display_name="Observer",
        scopes=V2_READ_SCOPES,
        bonjour=None,
        now=None,
    ):
        if now is None:
            now = int(time.time())

        requested_scopes = tuple(scopes)

        unknown = (
            set(requested_scopes)
            - set(V2_READ_SCOPES)
        )

        if unknown:
            raise ValueError(
                "unsupported v2 scope: "
                + ", ".join(
                    sorted(unknown)
                )
            )

        bootstrap_secret = b64url_encode(
            secrets.token_bytes(32)
        )

        expires_at = (
            now + PAIR_TTL_SECONDS
        )

        pending = {
            "secret_hash":
                self._secret_hash(
                    bootstrap_secret
                ),
            "expires_at": expires_at,
            "failed_attempts": 0,
            "display_name": display_name,
            "offered_scopes":
                list(requested_scopes),
        }

        with self._locked():
            state = self._read()
            state["pending"] = pending
            self._write(state)

        qr = build_pairing_qr(
            expires_at=expires_at,
            host=host,
            pin=pin,
            bootstrap_secret=
                bootstrap_secret,
            display_name=display_name,
            scopes=requested_scopes,
            bonjour=bonjour,
        )

        return {
            "qr": qr,
            "expires_at": expires_at,
            "offered_scopes":
                list(requested_scopes),
        }

    def get_device(
        self,
        device_id,
    ):
        with self._locked():
            state = self._read()
            device = (
                state
                .get("devices", {})
                .get(device_id)
            )

            if device is None:
                return None

            # Return a detached copy so callers cannot
            # mutate persistent state accidentally.
            return json.loads(
                json.dumps(device)
            )

    def touch_device(
        self,
        device_id,
        *,
        now=None,
        peer_address=None,
    ):
        if now is None:
            now = int(time.time())

        with self._locked():
            state = self._read()

            device = (
                state
                .get("devices", {})
                .get(device_id)
            )

            if (
                device is None
                or device.get("revoked")
            ):
                return False

            device["last_seen"] = now

            if peer_address is not None:
                device[
                    "last_address"
                ] = peer_address

            self._write(state)

        return True

    def revoke_device(
        self,
        device_id,
    ):
        with self._locked():
            state = self._read()

            device = (
                state
                .get("devices", {})
                .get(device_id)
            )

            if device is None:
                return False

            device["revoked"] = True

            # Destroy the credential when revoked.
            device.pop(
                "hmac_key",
                None,
            )

            self._write(state)

        return True

    def activate(
        self,
        *,
        secret,
        device_name,
        scopes,
        peer_address=None,
        now=None,
    ):
        if now is None:
            now = int(time.time())

        if (
            not isinstance(device_name, str)
            or not device_name.strip()
            or len(device_name) > 80
        ):
            raise PairingError(
                "invalid_device_name",
                400,
            )

        if not isinstance(scopes, list):
            raise PairingError(
                "invalid_scopes",
                400,
            )

        if not scopes:
            raise PairingError(
                "invalid_scopes",
                400,
            )

        if len(scopes) != len(set(scopes)):
            raise PairingError(
                "invalid_scopes",
                400,
            )

        with self._locked():
            state = self._read()
            pending = state.get(
                "pending"
            )

            if not pending:
                raise PairingError(
                    "pairing_not_pending",
                    401,
                )

            if now > int(
                pending["expires_at"]
            ):
                state["pending"] = None
                self._write(state)

                raise PairingError(
                    "pairing_expired",
                    401,
                )

            supplied_hash = (
                self._secret_hash(
                    secret
                )
            )

            if not hmac.compare_digest(
                supplied_hash,
                pending["secret_hash"],
            ):
                pending[
                    "failed_attempts"
                ] = (
                    int(
                        pending.get(
                            "failed_attempts",
                            0,
                        )
                    )
                    + 1
                )

                if (
                    pending[
                        "failed_attempts"
                    ]
                    >= PAIR_MAX_FAILURES
                ):
                    state[
                        "pending"
                    ] = None

                self._write(state)

                raise PairingError(
                    "invalid_bootstrap",
                    401,
                )

            offered = set(
                pending[
                    "offered_scopes"
                ]
            )

            requested = set(scopes)

            if not requested.issubset(
                offered
            ):
                raise PairingError(
                    "invalid_scope",
                    400,
                )

            device_id = (
                "d_"
                + b64url_encode(
                    secrets.token_bytes(
                        12
                    )
                )
            )

            hmac_key = b64url_encode(
                secrets.token_bytes(32)
            )

            devices = state.setdefault(
                "devices",
                {},
            )

            devices[device_id] = {
                "device_name":
                    device_name.strip(),
                "hmac_key":
                    hmac_key,
                "scopes":
                    list(scopes),
                "paired_at":
                    now,
                "last_seen":
                    now,
                "last_address":
                    peer_address,
                "revoked":
                    False,
            }

            # One successful activation consumes
            # the bootstrap secret permanently.
            state["pending"] = None

            self._write(state)

        return {
            "device_id":
                device_id,
            "hmac_key":
                hmac_key,
            "granted_scopes":
                list(scopes),
        }
