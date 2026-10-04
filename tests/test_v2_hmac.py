import json
import unittest
from pathlib import Path

from v2_crypto import (
    b64url_decode,
    body_sha256_hex,
    canonical_request_v2,
    hmac_signature_v2,
    verify_hmac_signature_v2,
)


ROOT = Path(__file__).resolve().parents[1]
VECTOR_FILE = ROOT / "vectors" / "v2-hmac.json"


class ObserverV2HMACTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.vector = json.loads(
            VECTOR_FILE.read_text()
        )

    def test_interoperability_vector(self):
        v = self.vector

        key = bytes.fromhex(
            v["hmac_key_hex"]
        )

        body = v["body_utf8"].encode(
            "utf-8"
        )

        canonical = canonical_request_v2(
            v["method"],
            v["request_target"],
            v["timestamp"],
            v["nonce_base64url"],
            v["device_id"],
            body,
        )

        self.assertEqual(
            canonical.decode("utf-8"),
            v["canonical"],
        )

        self.assertEqual(
            body_sha256_hex(body),
            v["body_sha256_hex"],
        )

        signature = hmac_signature_v2(
            key,
            v["method"],
            v["request_target"],
            v["timestamp"],
            v["nonce_base64url"],
            v["device_id"],
            body,
        )

        self.assertEqual(
            signature,
            v["signature_base64url"],
        )

        self.assertEqual(
            b64url_decode(signature).hex(),
            v["signature_hex"],
        )

    def test_signature_verifies(self):
        v = self.vector
        key = bytes.fromhex(
            v["hmac_key_hex"]
        )

        self.assertTrue(
            verify_hmac_signature_v2(
                key,
                v["signature_base64url"],
                v["method"],
                v["request_target"],
                v["timestamp"],
                v["nonce_base64url"],
                v["device_id"],
                v["body_utf8"].encode("utf-8"),
            )
        )

    def test_percent_encoding_is_not_normalized(self):
        v = self.vector
        key = bytes.fromhex(
            v["hmac_key_hex"]
        )

        changed_target = (
            "/v2/status?"
            "detail=mining/rewards&limit=10"
        )

        changed_signature = hmac_signature_v2(
            key,
            v["method"],
            changed_target,
            v["timestamp"],
            v["nonce_base64url"],
            v["device_id"],
            b"",
        )

        self.assertNotEqual(
            changed_signature,
            v["signature_base64url"],
        )

    def test_query_order_is_not_normalized(self):
        v = self.vector
        key = bytes.fromhex(
            v["hmac_key_hex"]
        )

        reordered_target = (
            "/v2/status?"
            "limit=10&detail=mining%2Frewards"
        )

        reordered_signature = hmac_signature_v2(
            key,
            v["method"],
            reordered_target,
            v["timestamp"],
            v["nonce_base64url"],
            v["device_id"],
            b"",
        )

        self.assertNotEqual(
            reordered_signature,
            v["signature_base64url"],
        )

    def test_bare_question_mark_rejected(self):
        with self.assertRaises(ValueError):
            canonical_request_v2(
                "GET",
                "/v2/status?",
                "1791068453",
                "AAECAwQFBgcICQoLDA0ODw",
                "d_test_casberi_01",
                b"",
            )

    def test_fragment_rejected(self):
        with self.assertRaises(ValueError):
            canonical_request_v2(
                "GET",
                "/v2/status#fragment",
                "1791068453",
                "AAECAwQFBgcICQoLDA0ODw",
                "d_test_casberi_01",
                b"",
            )


if __name__ == "__main__":
    unittest.main()
