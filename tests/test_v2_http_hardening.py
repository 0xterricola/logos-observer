import unittest
from email.message import Message

from v2_pairing import PairingError
from v2_server import (
    MAX_JSON_BODY,
    _json_body_length,
)


def make_headers(*pairs):
    headers = Message()

    for name, value in pairs:
        headers.add_header(
            name,
            value,
        )

    return headers


class ObserverV2HTTPHardeningTests(
    unittest.TestCase
):
    def test_valid_content_length(self):
        headers = make_headers(
            (
                "Content-Length",
                "123",
            )
        )

        self.assertEqual(
            _json_body_length(
                headers
            ),
            123,
        )

    def test_transfer_encoding_rejected(self):
        headers = make_headers(
            (
                "Transfer-Encoding",
                "chunked",
            ),
            (
                "Content-Length",
                "10",
            ),
        )

        with self.assertRaises(
            PairingError
        ) as ctx:
            _json_body_length(
                headers
            )

        self.assertEqual(
            ctx.exception.code,
            "invalid_json",
        )

        self.assertEqual(
            ctx.exception.status_code,
            400,
        )

    def test_missing_content_length_rejected(self):
        headers = make_headers()

        with self.assertRaises(
            PairingError
        ):
            _json_body_length(
                headers
            )

    def test_duplicate_content_length_rejected(self):
        headers = make_headers(
            (
                "Content-Length",
                "10",
            ),
            (
                "Content-Length",
                "10",
            ),
        )

        with self.assertRaises(
            PairingError
        ):
            _json_body_length(
                headers
            )

    def test_non_decimal_content_length_rejected(self):
        for value in (
            "-1",
            "+1",
            "1, 1",
            " 10",
            "10 ",
            "abc",
            "",
        ):
            with self.subTest(
                value=value,
            ):
                headers = make_headers(
                    (
                        "Content-Length",
                        value,
                    )
                )

                with self.assertRaises(
                    PairingError
                ):
                    _json_body_length(
                        headers
                    )

    def test_zero_and_oversized_bodies_rejected(self):
        for value in (
            "0",
            str(
                MAX_JSON_BODY + 1
            ),
        ):
            with self.subTest(
                value=value,
            ):
                headers = make_headers(
                    (
                        "Content-Length",
                        value,
                    )
                )

                with self.assertRaises(
                    PairingError
                ):
                    _json_body_length(
                        headers
                    )


if __name__ == "__main__":
    unittest.main()
