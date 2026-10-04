import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import (
    parse_qs,
    urlsplit,
)

from v2_auth import (
    AuthError,
    NonceStore,
    authenticate_v2_request,
)
from v2_crypto import (
    b64url_decode,
    b64url_encode,
    hmac_signature_v2,
)
from v2_pairing import (
    PairingStore,
)


class ObserverV2AuthTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            TemporaryDirectory()
        )

        self.state_dir = Path(
            self.tempdir.name
        )

        self.pairing = PairingStore(
            self.state_dir
        )

        self.nonces = NonceStore(
            self.state_dir
        )

        offer = (
            self.pairing
            .create_offer(
                host="127.0.0.1:8443",
                pin="sha256/test",
                now=1000,
            )
        )

        secret = parse_qs(
            urlsplit(
                offer["qr"]
            ).query
        )["s"][0]

        result = (
            self.pairing
            .activate(
                secret=secret,
                device_name=(
                    "Casberi Test"
                ),
                scopes=[
                    "node.status.read",
                    "network.status.read",
                ],
                peer_address=
                    "127.0.0.1",
                now=1001,
            )
        )

        self.device_id = result[
            "device_id"
        ]

        self.key = b64url_decode(
            result["hmac_key"]
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def signed_headers(
        self,
        *,
        method="GET",
        target="/v2/status",
        timestamp="1100",
        nonce_bytes=None,
        body=b"",
        key=None,
    ):
        if nonce_bytes is None:
            nonce_bytes = bytes(
                range(16)
            )

        nonce = b64url_encode(
            nonce_bytes
        )

        if key is None:
            key = self.key

        signature = (
            hmac_signature_v2(
                key,
                method,
                target,
                timestamp,
                nonce,
                self.device_id,
                body,
            )
        )

        return {
            "X-Observer-Device":
                self.device_id,
            "X-Observer-Timestamp":
                timestamp,
            "X-Observer-Nonce":
                nonce,
            "X-Observer-Signature":
                signature,
        }

    def authenticate(
        self,
        headers,
        *,
        required_scope=None,
        now=1100,
        target="/v2/status",
        body=b"",
    ):
        return authenticate_v2_request(
            pairing_store=
                self.pairing,
            nonce_store=
                self.nonces,
            method="GET",
            request_target=target,
            headers=headers,
            body=body,
            required_scope=
                required_scope,
            peer_address=
                "192.168.1.50",
            now=now,
        )

    def test_valid_request(self):
        context = self.authenticate(
            self.signed_headers()
        )

        self.assertEqual(
            context["device_id"],
            self.device_id,
        )

        device = (
            self.pairing
            .get_device(
                self.device_id
            )
        )

        self.assertEqual(
            device["last_seen"],
            1100,
        )

        self.assertEqual(
            device["last_address"],
            "192.168.1.50",
        )

    def test_bad_signature(self):
        headers = (
            self.signed_headers()
        )

        headers[
            "X-Observer-Signature"
        ] = "definitely-wrong"

        with self.assertRaises(
            AuthError
        ) as ctx:
            self.authenticate(
                headers
            )

        self.assertEqual(
            ctx.exception.code,
            "bad_signature",
        )

    def test_clock_skew(self):
        headers = (
            self.signed_headers(
                timestamp="1000"
            )
        )

        with self.assertRaises(
            AuthError
        ) as ctx:
            self.authenticate(
                headers,
                now=1201,
            )

        self.assertEqual(
            ctx.exception.code,
            "clock_skew",
        )

    def test_scope_denied(self):
        headers = (
            self.signed_headers()
        )

        with self.assertRaises(
            AuthError
        ) as ctx:
            self.authenticate(
                headers,
                required_scope=(
                    "mining.status.read"
                ),
            )

        self.assertEqual(
            ctx.exception.code,
            "scope",
        )

        self.assertEqual(
            ctx.exception.status_code,
            403,
        )

    def test_replay_rejected(self):
        headers = (
            self.signed_headers()
        )

        self.authenticate(
            headers
        )

        with self.assertRaises(
            AuthError
        ) as ctx:
            self.authenticate(
                headers
            )

        self.assertEqual(
            ctx.exception.code,
            "replay",
        )

    def test_replay_survives_store_reopen(
        self,
    ):
        headers = (
            self.signed_headers()
        )

        self.authenticate(
            headers
        )

        reopened = NonceStore(
            self.state_dir
        )

        with self.assertRaises(
            AuthError
        ) as ctx:
            authenticate_v2_request(
                pairing_store=
                    self.pairing,
                nonce_store=
                    reopened,
                method="GET",
                request_target=
                    "/v2/status",
                headers=headers,
                body=b"",
                now=1100,
            )

        self.assertEqual(
            ctx.exception.code,
            "replay",
        )

    def test_revoked_device(self):
        self.assertTrue(
            self.pairing
            .revoke_device(
                self.device_id
            )
        )

        headers = (
            self.signed_headers()
        )

        with self.assertRaises(
            AuthError
        ) as ctx:
            self.authenticate(
                headers
            )

        self.assertEqual(
            ctx.exception.code,
            "revoked",
        )


if __name__ == "__main__":
    unittest.main()
