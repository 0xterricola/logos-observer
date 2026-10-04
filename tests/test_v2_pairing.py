import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import (
    parse_qs,
    urlsplit,
)

from v2_pairing import (
    PAIR_MAX_FAILURES,
    PairingError,
    PairingStore,
    V2_READ_SCOPES,
    build_pairing_qr,
)


class ObserverV2PairingTests(
    unittest.TestCase
):
    def test_qr_contract(self):
        qr = build_pairing_qr(
            expires_at=1791068753,
            host="192.168.1.20:8081",
            bonjour=(
                "Logos Observer."
                "_logos-observer._tcp"
            ),
            pin=(
                "sha256/"
                "b5b_xWoDK7EJ11lQXxjG0-"
                "VqRbq6LqcNFrMf7pYBC8o"
            ),
            bootstrap_secret=(
                "AAECAwQFBgcICQoLDA0ODxAR"
                "EhMUFRYXGBkaGxwdHh8"
            ),
            display_name="Observer",
            scopes=V2_READ_SCOPES,
        )

        self.assertLessEqual(
            len(qr),
            300,
        )

        parsed = urlsplit(qr)

        self.assertEqual(
            parsed.scheme,
            "logos-observer",
        )

        self.assertEqual(
            parsed.netloc,
            "pair",
        )

        params = parse_qs(
            parsed.query
        )

        self.assertEqual(
            params["v"],
            ["2"],
        )

        self.assertEqual(
            params["h"],
            ["192.168.1.20:8081"],
        )

        self.assertEqual(
            params["sc"],
            [
                ",".join(
                    V2_READ_SCOPES
                )
            ],
        )

    def test_activation_is_single_use(self):
        with TemporaryDirectory() as td:
            store = PairingStore(
                Path(td)
            )

            offer = store.create_offer(
                host="127.0.0.1:8443",
                pin="sha256/test",
                now=1000,
            )

            params = parse_qs(
                urlsplit(
                    offer["qr"]
                ).query
            )

            secret = params["s"][0]

            result = store.activate(
                secret=secret,
                device_name=(
                    "Casberi Test"
                ),
                scopes=list(
                    V2_READ_SCOPES
                ),
                peer_address=
                    "127.0.0.1",
                now=1001,
            )

            self.assertTrue(
                result[
                    "device_id"
                ].startswith("d_")
            )

            self.assertEqual(
                len(
                    result[
                        "hmac_key"
                    ]
                ),
                43,
            )

            with self.assertRaises(
                PairingError
            ) as ctx:
                store.activate(
                    secret=secret,
                    device_name="Again",
                    scopes=list(
                        V2_READ_SCOPES
                    ),
                    now=1002,
                )

            self.assertEqual(
                ctx.exception.code,
                "pairing_not_pending",
            )

    def test_scope_subset(self):
        with TemporaryDirectory() as td:
            store = PairingStore(
                Path(td)
            )

            offer = store.create_offer(
                host="127.0.0.1:8443",
                pin="sha256/test",
                now=1000,
            )

            secret = parse_qs(
                urlsplit(
                    offer["qr"]
                ).query
            )["s"][0]

            wanted = [
                "node.status.read",
                "network.status.read",
            ]

            result = store.activate(
                secret=secret,
                device_name="Phone",
                scopes=wanted,
                now=1001,
            )

            self.assertEqual(
                result[
                    "granted_scopes"
                ],
                wanted,
            )

    def test_five_failures_void_offer(
        self,
    ):
        with TemporaryDirectory() as td:
            store = PairingStore(
                Path(td)
            )

            offer = store.create_offer(
                host="127.0.0.1:8443",
                pin="sha256/test",
                now=1000,
            )

            good_secret = parse_qs(
                urlsplit(
                    offer["qr"]
                ).query
            )["s"][0]

            for _ in range(
                PAIR_MAX_FAILURES
            ):
                with self.assertRaises(
                    PairingError
                ) as ctx:
                    store.activate(
                        secret="wrong",
                        device_name="Phone",
                        scopes=[
                            "node.status.read"
                        ],
                        now=1001,
                    )

                self.assertEqual(
                    ctx.exception.code,
                    "invalid_bootstrap",
                )

            with self.assertRaises(
                PairingError
            ) as ctx:
                store.activate(
                    secret=good_secret,
                    device_name="Phone",
                    scopes=[
                        "node.status.read"
                    ],
                    now=1002,
                )

            self.assertEqual(
                ctx.exception.code,
                "pairing_not_pending",
            )

    def test_expired_offer(self):
        with TemporaryDirectory() as td:
            store = PairingStore(
                Path(td)
            )

            offer = store.create_offer(
                host="127.0.0.1:8443",
                pin="sha256/test",
                now=1000,
            )

            secret = parse_qs(
                urlsplit(
                    offer["qr"]
                ).query
            )["s"][0]

            with self.assertRaises(
                PairingError
            ) as ctx:
                store.activate(
                    secret=secret,
                    device_name="Phone",
                    scopes=[
                        "node.status.read"
                    ],
                    now=1301,
                )

            self.assertEqual(
                ctx.exception.code,
                "pairing_expired",
            )


if __name__ == "__main__":
    unittest.main()
