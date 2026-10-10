#!/usr/bin/env python3

import unittest
from unittest.mock import patch

import v2_rewards_collector as collector


class RewardsCollectorTests(
    unittest.TestCase
):
    def test_collects_sanitized_aggregates(
        self,
    ):
        pow_notes = {
            "notes": [
                {
                    "id": "pow-1",
                    "value": "1000000000",
                },
                {
                    "id": "pow-2",
                    "value": "2623374900",
                },
                {
                    "id": "pow-3",
                    "value": "500000000",
                },
            ],
        }

        leader_notes = {
            "notes": [
                {
                    "id": "pow-1",
                    "value": "1000000000",
                },
                {
                    "id": "pow-2",
                    "value": "2623374900",
                },
                {
                    "id": "other-wallet-note",
                    "value": "1170680231",
                },
            ],
            "total_value": "4794055131",
        }

        def fake_call(
            method,
            *args,
        ):
            if method == "wallet_get_notes":
                self.assertEqual(
                    args,
                    ("PUBLIC-POW-KEY", ""),
                )
                return pow_notes

            if (
                method
                == "wallet_get_leader_aged_notes"
            ):
                self.assertEqual(
                    args,
                    ("",),
                )
                return leader_notes

            self.fail(
                f"unexpected method: {method}"
            )

        with (
            patch.object(
                collector,
                "_pow_claim_key",
                return_value="PUBLIC-POW-KEY",
            ),
            patch.object(
                collector,
                "_call",
                side_effect=fake_call,
            ),
        ):
            result = collector.collect()

        self.assertEqual(
            result,
            {
                "mining_notes": 3,
                "consensus": {
                    "pow_eligible_notes": 2,
                    "pow_eligible_balance_atoms":
                        "3623374900",
                    "pow_aging_notes": 1,
                    "wallet_eligible_notes": 3,
                    "wallet_eligible_balance_atoms":
                        "4794055131",
                },
            },
        )

        serialized = repr(result)

        self.assertNotIn(
            "PUBLIC-POW-KEY",
            serialized,
        )
        self.assertNotIn(
            "pow-1",
            serialized,
        )
        self.assertNotIn(
            "other-wallet-note",
            serialized,
        )


if __name__ == "__main__":
    unittest.main()

class RewardsCollectorRpcTests(unittest.TestCase):

    @patch("v2_rewards_collector.subprocess.run")
    def test_current_blockchain_rpc_envelope(self, mock_run):
        import json

        mock_run.return_value.stdout = json.dumps({
            "success": True,
            "error": None,
            "value": json.dumps({"notes": []}),
        })

        result = collector._call(
            "wallet_get_leader_aged_notes", ""
        )

        self.assertEqual(result, {"notes": []})

    @patch("v2_rewards_collector.subprocess.run")
    def test_nested_rpc_envelope(self, mock_run):
        import json

        mock_run.return_value.stdout = json.dumps({
            "result": {
                "success": True,
                "error": None,
                "value": json.dumps({"notes": []}),
            }
        })

        result = collector._call(
            "wallet_get_leader_aged_notes", ""
        )

        self.assertEqual(result, {"notes": []})

    @patch("v2_rewards_collector.subprocess.run")
    def test_rpc_error_is_rejected(self, mock_run):
        import json

        mock_run.return_value.stdout = json.dumps({
            "success": False,
            "error": "Unknown wallet address.",
            "value": None,
        })

        with self.assertRaises(RuntimeError):
            collector._call(
                "wallet_get_notes", "invalid", ""
            )
