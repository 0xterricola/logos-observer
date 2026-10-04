import tempfile
import unittest

from cryptography import x509
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric import ec

from v2_tls import (
    ensure_tls_identity,
    load_certificate,
    spki_pin_from_certificate,
)


class ObserverV2TLSTests(unittest.TestCase):
    def test_identity_is_p256_and_persistent(self):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)

            first = ensure_tls_identity(
                state,
                dns_names=[
                    "logos-observer.local",
                ],
                ip_addresses=[
                    "127.0.0.1",
                ],
            )

            first_key = first[
                "key_path"
            ].read_bytes()

            first_pin = first["pin"]

            second = ensure_tls_identity(
                state,
                dns_names=[
                    "logos-observer.local",
                ],
                ip_addresses=[
                    "127.0.0.1",
                ],
            )

            second_key = second[
                "key_path"
            ].read_bytes()

            self.assertEqual(
                first_key,
                second_key,
            )

            self.assertEqual(
                first_pin,
                second["pin"],
            )

            cert = load_certificate(
                second["cert_path"]
            )

            public_key = cert.public_key()

            self.assertIsInstance(
                public_key,
                ec.EllipticCurvePublicKey,
            )

            self.assertIsInstance(
                public_key.curve,
                ec.SECP256R1,
            )

    def test_pin_format(self):
        with tempfile.TemporaryDirectory() as td:
            identity = ensure_tls_identity(
                Path(td)
            )

            pin = identity["pin"]

            self.assertTrue(
                pin.startswith("sha256/")
            )

            encoded = pin.split("/", 1)[1]

            self.assertNotIn("=", encoded)

    def test_pin_matches_certificate(self):
        with tempfile.TemporaryDirectory() as td:
            identity = ensure_tls_identity(
                Path(td)
            )

            cert = load_certificate(
                identity["cert_path"]
            )

            self.assertEqual(
                identity["pin"],
                spki_pin_from_certificate(cert),
            )


if __name__ == "__main__":
    unittest.main()


class ObserverV2TLSRenewalTests(
    unittest.TestCase
):
    def test_new_san_preserves_spki_pin(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            state = Path(td)

            first = ensure_tls_identity(
                state,
                dns_names=[
                    "logos-observer.local"
                ],
                ip_addresses=[
                    "127.0.0.1"
                ],
            )

            second = ensure_tls_identity(
                state,
                dns_names=[
                    "logos-observer.local"
                ],
                ip_addresses=[
                    "192.168.1.160"
                ],
            )

            self.assertEqual(
                first["pin"],
                second["pin"],
            )

            san = (
                second["certificate"]
                .extensions
                .get_extension_for_class(
                    x509.SubjectAlternativeName
                )
                .value
            )

            ips = {
                str(value)
                for value in san.get_values_for_type(
                    x509.IPAddress
                )
            }

            self.assertIn(
                "192.168.1.160",
                ips,
            )
