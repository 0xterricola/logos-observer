import json
import unittest
from pathlib import Path

from v2_tls import (
    load_certificate,
    spki_pin_from_certificate,
)


ROOT = Path(__file__).resolve().parents[1]


class ObserverV2SPKIVectorTests(unittest.TestCase):
    def test_sample_certificate_pin(self):
        vector = json.loads(
            (
                ROOT
                / "vectors"
                / "v2-spki.json"
            ).read_text()
        )

        cert = load_certificate(
            ROOT
            / "vectors"
            / vector["certificate"]
        )

        computed = spki_pin_from_certificate(
            cert
        )

        self.assertEqual(
            computed,
            vector["expected_pin"],
        )


if __name__ == "__main__":
    unittest.main()
