#!/usr/bin/env python3

import os
import sqlite3
import time
from contextlib import closing
from pathlib import Path

from v2_crypto import (
    b64url_decode,
    verify_hmac_signature_v2,
)


CLOCK_SKEW_SECONDS = 120
NONCE_TTL_SECONDS = 5 * 60


class AuthError(Exception):
    def __init__(self, code, status_code):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


class NonceStore:
    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.path = (
            self.state_dir
            / "v2-nonces.sqlite3"
        )

        self._initialize()

    def _connect(self):
        connection = sqlite3.connect(
            self.path,
            timeout=5,
            isolation_level=None,
        )

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        return connection

    def _initialize(self):
        with closing(self._connect()) as db:
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

        os.chmod(
            self.path,
            0o600,
        )

    def consume(
        self,
        device_id,
        nonce,
        *,
        now=None,
    ):
        if now is None:
            now = int(time.time())

        cutoff = (
            now - NONCE_TTL_SECONDS
        )

        with closing(self._connect()) as db:
            db.execute(
                "BEGIN IMMEDIATE"
            )

            try:
                db.execute(
                    """
                    DELETE FROM seen_nonces
                    WHERE seen_at < ?
                    """,
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
                    db.execute(
                        "ROLLBACK"
                    )
                    return False

                db.execute(
                    "COMMIT"
                )
                return True

            except Exception:
                try:
                    db.execute(
                        "ROLLBACK"
                    )
                except sqlite3.Error:
                    pass

                raise


def authenticate_v2_request(
    *,
    pairing_store,
    nonce_store,
    method,
    request_target,
    headers,
    body,
    required_scope=None,
    peer_address=None,
    now=None,
):
    """
    Frozen v2 verification order:

      1. device
      2. timestamp
      3. signature
      4. scope
      5. consume nonce
      6. touch device / allow node read
    """

    if now is None:
        now = int(time.time())

    device_id = headers.get(
        "X-Observer-Device"
    )

    if not device_id:
        raise AuthError(
            "revoked",
            401,
        )

    device = pairing_store.get_device(
        device_id
    )

    if (
        not device
        or device.get("revoked")
    ):
        raise AuthError(
            "revoked",
            401,
        )

    timestamp_text = headers.get(
        "X-Observer-Timestamp"
    )

    try:
        timestamp = int(
            timestamp_text
        )
    except (
        TypeError,
        ValueError,
    ):
        raise AuthError(
            "clock_skew",
            401,
        )

    if abs(now - timestamp) > (
        CLOCK_SKEW_SECONDS
    ):
        raise AuthError(
            "clock_skew",
            401,
        )

    nonce = headers.get(
        "X-Observer-Nonce"
    )

    signature = headers.get(
        "X-Observer-Signature"
    )

    if (
        not isinstance(nonce, str)
        or not isinstance(
            signature,
            str,
        )
    ):
        raise AuthError(
            "bad_signature",
            401,
        )

    try:
        hmac_key = b64url_decode(
            device["hmac_key"]
        )
    except Exception:
        raise AuthError(
            "revoked",
            401,
        )

    if not verify_hmac_signature_v2(
        hmac_key,
        signature,
        method,
        request_target,
        timestamp_text,
        nonce,
        device_id,
        body,
    ):
        raise AuthError(
            "bad_signature",
            401,
        )

    if (
        required_scope is not None
        and required_scope
            not in device.get(
                "scopes",
                [],
            )
    ):
        raise AuthError(
            "scope",
            403,
        )

    # Nonce format is checked only after the
    # request signature has authenticated it.
    try:
        nonce_bytes = b64url_decode(
            nonce
        )
    except Exception:
        raise AuthError(
            "bad_signature",
            401,
        )

    if len(nonce_bytes) != 16:
        raise AuthError(
            "bad_signature",
            401,
        )

    if not nonce_store.consume(
        device_id,
        nonce,
        now=now,
    ):
        raise AuthError(
            "replay",
            401,
        )

    pairing_store.touch_device(
        device_id,
        now=now,
        peer_address=peer_address,
    )

    return {
        "device_id": device_id,
        "device": pairing_store.get_device(
            device_id
        ),
    }
