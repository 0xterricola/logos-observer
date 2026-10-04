import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import (
    parse_qs,
    urlsplit,
)

from v2_pair_cli import (
    certificate_names_for_host,
    create_local_pairing_offer,
    endpoint_for_host,
)


class ObserverV2PairCLITests(
    unittest.TestCase
):
    def test_offer_uses_identity_pin_and_hashes_secret(
        self,
    ):
        with TemporaryDirectory() as td:
            state_dir = Path(td)

            offer = create_local_pairing_offer(
                state_dir=state_dir,
                advertise_host=
                    "192.168.1.160",
                port=8443,
                display_name=
                    "Logos Observer",
                now=1000,
            )

            parsed = urlsplit(
                offer["qr"]
            )

            params = parse_qs(
                parsed.query
            )

            self.assertEqual(
                params["h"],
                [
                    "192.168.1.160:8443"
                ],
            )

            self.assertEqual(
                params["pin"],
                [
                    offer["pin"]
                ],
            )

            self.assertEqual(
                params["exp"],
                ["1300"],
            )

            secret = params["s"][0]

            state = json.loads(
                (
                    state_dir
                    / "v2-pairing.json"
                ).read_text()
            )

            pending = state[
                "pending"
            ]

            self.assertNotIn(
                secret,
                json.dumps(state),
            )

            self.assertIn(
                "secret_hash",
                pending,
            )

    def test_identity_pin_is_persistent(
        self,
    ):
        with TemporaryDirectory() as td:
            state_dir = Path(td)

            first = create_local_pairing_offer(
                state_dir=state_dir,
                advertise_host=
                    "192.168.1.160",
                port=8443,
                display_name="Observer",
                now=1000,
            )

            second = create_local_pairing_offer(
                state_dir=state_dir,
                advertise_host=
                    "192.168.1.160",
                port=8443,
                display_name="Observer",
                now=1100,
            )

            self.assertEqual(
                first["pin"],
                second["pin"],
            )

    def test_host_helpers(self):
        dns, ips = (
            certificate_names_for_host(
                "192.168.1.160"
            )
        )

        self.assertEqual(
            ips,
            ["192.168.1.160"],
        )

        self.assertIn(
            "logos-observer.local",
            dns,
        )

        self.assertEqual(
            endpoint_for_host(
                "192.168.1.160",
                8443,
            ),
            "192.168.1.160:8443",
        )


if __name__ == "__main__":
    unittest.main()
