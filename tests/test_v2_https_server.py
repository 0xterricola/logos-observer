import http.client
import json
import ssl
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import (
    parse_qs,
    urlsplit,
)

from v2_auth import NonceStore
from v2_crypto import (
    b64url_decode,
    b64url_encode,
    hmac_signature_v2,
)
from v2_pairing import PairingStore
from v2_server import V2Handler
from v2_tls import (
    create_server_ssl_context,
    ensure_tls_identity,
)


class ObserverV2HTTPSServerTests(
    unittest.TestCase
):
    def setUp(self):
        self.tempdir = (
            tempfile.TemporaryDirectory()
        )

        state_dir = Path(
            self.tempdir.name
        )

        identity = ensure_tls_identity(
            state_dir,
            common_name=(
                "Logos Observer Test"
            ),
            dns_names=[
                "localhost",
            ],
            ip_addresses=[
                "127.0.0.1",
            ],
        )

        self.pairing_store = (
            PairingStore(
                state_dir
            )
        )

        self.server = (
            ThreadingHTTPServer(
                (
                    "127.0.0.1",
                    0,
                ),
                V2Handler,
            )
        )

        self.server.pairing_store = (
            self.pairing_store
        )

        self.server.nonce_store = (
            NonceStore(
                state_dir
            )
        )

        class TestReader:
            def read_node(self):
                return {
                    "reachable": True,
                    "phase": "Following",
                    "height": 12345,
                    "tip": "abcdef",
                }

            def read_network(self):
                return {
                    "peers": 7,
                }

            def read_mining(self):
                return {
                    "is_mining": True,
                    "rewards_enabled": True,
                    "auto_claim": True,
                }

            def read_rewards(self):
                return {
                    "claimable_tickets": 0,
                    "slots_until_expiry": None,
                    "vouchers": 0,
                    "total_claimable": "0",
                }

            def read_blend(self):
                return None

        self.server.status_reader = (
            TestReader()
        )

        server_context = (
            create_server_ssl_context(
                identity[
                    "cert_path"
                ],
                identity[
                    "key_path"
                ],
            )
        )

        self.server.socket = (
            server_context.wrap_socket(
                self.server.socket,
                server_side=True,
            )
        )

        self.port = (
            self.server
            .server_address[1]
        )

        self.thread = (
            threading.Thread(
                target=(
                    self.server
                    .serve_forever
                ),
                daemon=True,
            )
        )

        self.thread.start()

        self.client_context = (
            ssl.create_default_context(
                cafile=str(
                    identity[
                        "cert_path"
                    ]
                )
            )
        )

        self.client_context.minimum_version = (
            ssl.TLSVersion.TLSv1_3
        )

        self.client_context.maximum_version = (
            ssl.TLSVersion.TLSv1_3
        )

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(
            timeout=2
        )
        self.tempdir.cleanup()

    def request(
        self,
        method,
        path,
        payload=None,
        headers=None,
    ):
        connection = (
            http.client
            .HTTPSConnection(
                "127.0.0.1",
                self.port,
                context=
                    self.client_context,
                timeout=2,
            )
        )

        connection.connect()

        tls_version = (
            connection.sock.version()
        )

        body = None
        headers = dict(
            headers or {}
        )

        if payload is not None:
            body = json.dumps(
                payload
            ).encode("utf-8")

            headers[
                "Content-Type"
            ] = "application/json"

            headers[
                "Content-Length"
            ] = str(len(body))

        connection.request(
            method,
            path,
            body=body,
            headers=headers,
        )

        response = (
            connection.getresponse()
        )

        response_body = (
            response
            .read()
            .decode("utf-8")
        )

        status = response.status

        connection.close()

        return (
            status,
            response_body,
            tls_version,
        )

    def test_health_over_tls13(
        self,
    ):
        status, body, tls = (
            self.request(
                "GET",
                "/health",
            )
        )

        self.assertEqual(
            status,
            200,
        )

        self.assertEqual(
            tls,
            "TLSv1.3",
        )

        self.assertIn(
            '"protocol":"logos-observer-v2"',
            body,
        )

    def test_unknown_route_is_404(
        self,
    ):
        status, body, tls = (
            self.request(
                "GET",
                "/not-a-route",
            )
        )

        self.assertEqual(
            tls,
            "TLSv1.3",
        )

        self.assertEqual(
            status,
            404,
        )

        self.assertEqual(
            body,
            '{"error":"not_found"}',
        )

    def pair_device(
        self,
        scopes,
    ):
        offer = (
            self.pairing_store
            .create_offer(
                host=(
                    "127.0.0.1:"
                    f"{self.port}"
                ),
                pin="sha256/test",
            )
        )

        secret = parse_qs(
            urlsplit(
                offer["qr"]
            ).query
        )["s"][0]

        status, body, _ = (
            self.request(
                "POST",
                "/v2/pair",
                {
                    "secret":
                        secret,
                    "device_name":
                        "Casberi Test",
                    "scopes":
                        list(scopes),
                },
            )
        )

        self.assertEqual(
            status,
            200,
        )

        return json.loads(body)

    def signed_headers(
        self,
        pairing,
        *,
        method,
        path,
        nonce_byte,
        timestamp,
    ):
        nonce = b64url_encode(
            bytes(
                [nonce_byte]
                * 16
            )
        )

        signature = (
            hmac_signature_v2(
                b64url_decode(
                    pairing[
                        "hmac_key"
                    ]
                ),
                method,
                path,
                str(timestamp),
                nonce,
                pairing[
                    "device_id"
                ],
                b"",
            )
        )

        return {
            "X-Observer-Device":
                pairing[
                    "device_id"
                ],
            "X-Observer-Timestamp":
                str(timestamp),
            "X-Observer-Nonce":
                nonce,
            "X-Observer-Signature":
                signature,
        }

    def test_authenticated_status(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
                "network.status.read",
            ]
        )

        now = int(time.time())

        headers = self.signed_headers(
            pairing,
            method="GET",
            path="/v2/status",
            nonce_byte=1,
            timestamp=now,
        )

        status, body, tls = (
            self.request(
                "GET",
                "/v2/status",
                headers=headers,
            )
        )

        self.assertEqual(
            tls,
            "TLSv1.3",
        )

        self.assertEqual(
            status,
            200,
        )

        payload = json.loads(body)

        self.assertEqual(
            payload["v"],
            2,
        )

        self.assertEqual(
            payload["node"][
                "height"
            ],
            12345,
        )

        self.assertEqual(
            payload["network"][
                "peers"
            ],
            7,
        )

        self.assertNotIn(
            "mining",
            payload,
        )

        self.assertNotIn(
            "rewards",
            payload,
        )

    def test_status_replay_rejected(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
            ]
        )

        now = int(time.time())

        headers = self.signed_headers(
            pairing,
            method="GET",
            path="/v2/status",
            nonce_byte=2,
            timestamp=now,
        )

        first, _, _ = self.request(
            "GET",
            "/v2/status",
            headers=headers,
        )

        second, body, _ = self.request(
            "GET",
            "/v2/status",
            headers=headers,
        )

        self.assertEqual(
            first,
            200,
        )

        self.assertEqual(
            second,
            401,
        )

        self.assertEqual(
            json.loads(body),
            {
                "error": "replay",
            },
        )

    def test_self_revoke(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
            ]
        )

        now = int(time.time())

        revoke_headers = (
            self.signed_headers(
                pairing,
                method="DELETE",
                path="/v2/device",
                nonce_byte=3,
                timestamp=now,
            )
        )

        status, body, _ = (
            self.request(
                "DELETE",
                "/v2/device",
                headers=
                    revoke_headers,
            )
        )

        self.assertEqual(
            status,
            200,
        )

        self.assertEqual(
            json.loads(body),
            {
                "revoked": True,
            },
        )

        status_headers = (
            self.signed_headers(
                pairing,
                method="GET",
                path="/v2/status",
                nonce_byte=4,
                timestamp=now,
            )
        )

        status, body, _ = (
            self.request(
                "GET",
                "/v2/status",
                headers=
                    status_headers,
            )
        )

        self.assertEqual(
            status,
            401,
        )

        self.assertEqual(
            json.loads(body),
            {
                "error": "revoked",
            },
        )


    def test_dedicated_read_routes(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
                "network.status.read",
                "mining.status.read",
                "rewards.status.read",
            ]
        )

        now = int(time.time())

        cases = [
            (
                "/v2/network",
                10,
                {
                    "peers": 7,
                },
            ),
            (
                "/v2/mining",
                11,
                {
                    "is_mining": True,
                    "rewards_enabled":
                        True,
                    "auto_claim": True,
                },
            ),
            (
                "/v2/rewards",
                12,
                {
                    "claimable_tickets":
                        0,
                    "slots_until_expiry":
                        None,
                    "vouchers": 0,
                    "total_claimable":
                        "0",
                },
            ),
        ]

        for path, nonce_byte, expected in cases:
            headers = self.signed_headers(
                pairing,
                method="GET",
                path=path,
                nonce_byte=nonce_byte,
                timestamp=now,
            )

            status, body, tls = (
                self.request(
                    "GET",
                    path,
                    headers=headers,
                )
            )

            self.assertEqual(
                tls,
                "TLSv1.3",
            )

            self.assertEqual(
                status,
                200,
            )

            self.assertEqual(
                json.loads(body),
                expected,
            )

    def test_dedicated_route_scope_denied(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
            ]
        )

        now = int(time.time())

        headers = self.signed_headers(
            pairing,
            method="GET",
            path="/v2/network",
            nonce_byte=20,
            timestamp=now,
        )

        status, body, _ = (
            self.request(
                "GET",
                "/v2/network",
                headers=headers,
            )
        )

        self.assertEqual(
            status,
            403,
        )

        self.assertEqual(
            json.loads(body),
            {
                "error": "scope",
            },
        )

    def test_blend_route_remains_reserved(
        self,
    ):
        import time

        pairing = self.pair_device(
            [
                "node.status.read",
            ]
        )

        now = int(time.time())

        headers = self.signed_headers(
            pairing,
            method="GET",
            path="/v2/blend",
            nonce_byte=21,
            timestamp=now,
        )

        status, body, _ = (
            self.request(
                "GET",
                "/v2/blend",
                headers=headers,
            )
        )

        self.assertEqual(
            status,
            404,
        )

        self.assertEqual(
            json.loads(body),
            {
                "error": "not_found",
            },
        )


    def test_pair_activation_over_tls(
        self,
    ):
        offer = (
            self.pairing_store
            .create_offer(
                host=(
                    "127.0.0.1:"
                    f"{self.port}"
                ),
                pin="sha256/test",
            )
        )

        secret = parse_qs(
            urlsplit(
                offer["qr"]
            ).query
        )["s"][0]

        status, body, tls = (
            self.request(
                "POST",
                "/v2/pair",
                {
                    "secret":
                        secret,
                    "device_name":
                        "Casberi Test",
                    "scopes": [
                        "node.status.read",
                        "network.status.read",
                        "mining.status.read",
                        "rewards.status.read",
                    ],
                },
            )
        )

        self.assertEqual(
            tls,
            "TLSv1.3",
        )

        self.assertEqual(
            status,
            200,
        )

        payload = json.loads(body)

        self.assertTrue(
            payload[
                "device_id"
            ].startswith("d_")
        )

        self.assertEqual(
            len(
                payload[
                    "hmac_key"
                ]
            ),
            43,
        )

        self.assertEqual(
            payload[
                "granted_scopes"
            ],
            [
                "node.status.read",
                "network.status.read",
                "mining.status.read",
                "rewards.status.read",
            ],
        )


if __name__ == "__main__":
    unittest.main()
