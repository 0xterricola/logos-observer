import ssl
import tempfile
import unittest
from pathlib import Path

from v2_tls import (
    create_server_ssl_context,
    ensure_tls_identity,
)


class ObserverV2TLSContextTests(
    unittest.TestCase
):
    def test_server_context_is_tls13_only(
        self,
    ):
        with tempfile.TemporaryDirectory() as td:
            identity = ensure_tls_identity(
                Path(td),
                ip_addresses=[
                    "127.0.0.1",
                ],
            )

            context = (
                create_server_ssl_context(
                    identity["cert_path"],
                    identity["key_path"],
                )
            )

            self.assertEqual(
                context.minimum_version,
                ssl.TLSVersion.TLSv1_3,
            )

            self.assertEqual(
                context.maximum_version,
                ssl.TLSVersion.TLSv1_3,
            )


if __name__ == "__main__":
    unittest.main()
