import unittest

from v2_status import (
    build_status_snapshot,
)


class GoodReader:
    def read_node(self):
        return {
            "reachable": True,
            "phase": "Following",
            "height": 184220,
            "tip":
                "9f3ce41a",
        }

    def read_network(self):
        return {
            "peers": 12,
        }

    def read_mining(self):
        return {
            "is_mining": True,
            "rewards_enabled": True,
            "auto_claim": False,
        }

    def read_rewards(self):
        return {
            "claimable_tickets": 3,
            "slots_until_expiry": 412,
            "vouchers": 2,
            "total_claimable":
                "15.000000",
        }

    def read_blend(self):
        return {
            "active": True,
        }


class BrokenMiningReader(
    GoodReader
):
    def read_mining(self):
        raise RuntimeError(
            "boom"
        )


class DownReader(GoodReader):
    def read_node(self):
        return {
            "reachable": False,
            "phase": "wrong",
            "height": 123,
            "tip": "wrong",
        }


class ObserverV2StatusTests(
    unittest.TestCase
):
    def device(self, *scopes):
        return {
            "scopes": list(scopes),
        }

    def test_all_granted_sections(
        self,
    ):
        result = (
            build_status_snapshot(
                device=self.device(
                    "node.status.read",
                    "network.status.read",
                    "mining.status.read",
                    "rewards.status.read",
                ),
                reader=GoodReader(),
                now=1791068453,
            )
        )

        self.assertEqual(
            result["v"],
            2,
        )

        self.assertEqual(
            result["observed_at"],
            "2026-10-03T23:00:53Z",
        )

        self.assertTrue(
            result["node"][
                "reachable"
            ]
        )

        self.assertEqual(
            result["network"][
                "peers"
            ],
            12,
        )

        self.assertTrue(
            result["mining"][
                "is_mining"
            ]
        )

        self.assertEqual(
            result["rewards"][
                "vouchers"
            ],
            2,
        )

    def test_ungranted_sections_omitted(
        self,
    ):
        result = (
            build_status_snapshot(
                device=self.device(
                    "node.status.read",
                ),
                reader=GoodReader(),
                now=1791068453,
            )
        )

        self.assertIn(
            "node",
            result,
        )

        self.assertNotIn(
            "network",
            result,
        )

        self.assertNotIn(
            "mining",
            result,
        )

        self.assertNotIn(
            "rewards",
            result,
        )

    def test_failed_granted_read_is_null(
        self,
    ):
        result = (
            build_status_snapshot(
                device=self.device(
                    "node.status.read",
                    "mining.status.read",
                ),
                reader=
                    BrokenMiningReader(),
                now=1791068453,
            )
        )

        self.assertIsNone(
            result["mining"]
        )

    def test_node_down_shape(
        self,
    ):
        result = (
            build_status_snapshot(
                device=self.device(
                    "node.status.read",
                    "network.status.read",
                    "mining.status.read",
                    "rewards.status.read",
                ),
                reader=DownReader(),
                now=1791068453,
            )
        )

        self.assertEqual(
            result["node"],
            {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            },
        )

        self.assertIsNone(
            result["network"]
        )

        self.assertIsNone(
            result["mining"]
        )

        self.assertIsNone(
            result["rewards"]
        )


if __name__ == "__main__":
    unittest.main()
