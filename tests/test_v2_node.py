import unittest

from v2_node import LogosNodeReader


TIP = (
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
    "0123456789abcdef"
)


class FixtureFetcher:
    def __init__(self, values):
        self.values = values
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)

        value = self.values[path]

        if isinstance(
            value,
            Exception,
        ):
            raise value

        return value


class ObserverV2NodeReaderTests(
    unittest.TestCase
):
    def make_reader(
        self,
        extra=None,
    ):
        values = {
            "/cryptarchia/info": {
                "phase": "Following",
                "cryptarchia_info": {
                    "state": "Online",
                    "height": 9809,
                    "slot": 320072,
                    "lib_slot": 316809,
                    "tip": TIP,
                },
            },
            "/network/info": {
                "n_peers": 462,
            },
            "/pow/status": {
                "is_mining": True,
                "are_rewards_enabled":
                    True,
                "auto_claim": {
                    "is_armed": True,
                },
            },
            (
                "/pow/rewards/"
                "claimable"
            ): {
                "claimable_tickets":
                    2,
                "slots_until_expiry":
                    [412, 900],
            },
            (
                "/leader/claim/"
                "vouchers?tip="
                + TIP
            ): {
                "tip": TIP,
                "vouchers": [
                    {
                        "secret":
                            "must-not-leak"
                    },
                    {
                        "secret":
                            "must-not-leak"
                    },
                ],
                "reward_amount":
                    4928,
                "total_claimable":
                    9856,
            },
        }

        if extra:
            values.update(extra)

        fetcher = FixtureFetcher(
            values
        )

        reader = LogosNodeReader(
            fetch_json=fetcher,
            cache_ttl=10,
        )

        return (
            reader,
            fetcher,
        )

    def test_upstream_opener_disables_environment_proxies(
        self,
    ):
        from unittest.mock import patch

        sentinel_handler = object()
        sentinel_opener = object()

        with (
            patch(
                "v2_node.ProxyHandler",
                return_value=
                    sentinel_handler,
            ) as proxy_handler,
            patch(
                "v2_node.build_opener",
                return_value=
                    sentinel_opener,
            ) as build_opener,
        ):
            reader = LogosNodeReader(
                upstream=
                    "http://127.0.0.1:8080"
            )

        proxy_handler.assert_called_once_with(
            {}
        )

        build_opener.assert_called_once_with(
            sentinel_handler
        )

        self.assertIs(
            reader._opener,
            sentinel_opener,
        )

    def test_concurrent_same_path_fetch_is_single_flight(
        self,
    ):
        import threading
        import time

        calls = 0
        calls_lock = threading.Lock()

        expected = {
            "n_peers": 12,
        }

        def fetch(path):
            nonlocal calls

            self.assertEqual(
                path,
                "/network/info",
            )

            with calls_lock:
                calls += 1

            # Keep the first request in flight long enough for
            # the other worker threads to contend for the same
            # path lock.
            time.sleep(0.10)

            return expected

        reader = LogosNodeReader(
            fetch_json=fetch,
            cache_ttl=10,
        )

        worker_count = 8
        start = threading.Barrier(
            worker_count
        )

        results = [None] * worker_count
        errors = [None] * worker_count

        def worker(index):
            try:
                start.wait(
                    timeout=5,
                )

                results[index] = (
                    reader._fetch(
                        "/network/info"
                    )
                )
            except Exception as exc:
                errors[index] = exc

        threads = [
            threading.Thread(
                target=worker,
                args=(index,),
            )
            for index
            in range(worker_count)
        ]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join(
                timeout=5,
            )

        for thread in threads:
            self.assertFalse(
                thread.is_alive()
            )

        self.assertEqual(
            errors,
            [None] * worker_count,
        )

        self.assertEqual(
            calls,
            1,
        )

        self.assertEqual(
            results,
            [expected] * worker_count,
        )


    def test_node_mapping(self):
        reader, _ = (
            self.make_reader()
        )

        self.assertEqual(
            reader.read_node(),
            {
                "reachable": True,
                "phase": "Following",
                "height": 9809,
                "tip": TIP,
            },
        )

    def test_network_mapping(self):
        reader, _ = (
            self.make_reader()
        )

        self.assertEqual(
            reader.read_network(),
            {
                "peers": 462,
            },
        )

    def test_mining_mapping(self):
        reader, _ = (
            self.make_reader()
        )

        self.assertEqual(
            reader.read_mining(),
            {
                "is_mining": True,
                "rewards_enabled":
                    True,
                "auto_claim": True,
            },
        )

    def test_rewards_are_sanitized(
        self,
    ):
        reader, _ = (
            self.make_reader()
        )

        result = (
            reader.read_rewards()
        )

        self.assertEqual(
            result,
            {
                "claimable_tickets":
                    2,
                "slots_until_expiry":
                    412,
                "vouchers": 2,
                "total_claimable":
                    "9856",
            },
        )

        serialized = repr(result)

        self.assertNotIn(
            "must-not-leak",
            serialized,
        )

        self.assertNotIn(
            "reward_amount",
            result,
        )

    def test_no_expiry_becomes_null(
        self,
    ):
        reader, _ = (
            self.make_reader(
                {
                    (
                        "/pow/rewards/"
                        "claimable"
                    ): {
                        "claimable_tickets":
                            0,
                        "slots_until_expiry":
                            [],
                    },
                    (
                        "/leader/claim/"
                        "vouchers?tip="
                        + TIP
                    ): {
                        "tip": TIP,
                        "vouchers": [],
                        "reward_amount":
                            4928,
                        "total_claimable":
                            0,
                    },
                }
            )
        )

        result = (
            reader.read_rewards()
        )

        self.assertIsNone(
            result[
                "slots_until_expiry"
            ]
        )

        self.assertEqual(
            result[
                "total_claimable"
            ],
            "0",
        )

    def test_tip_is_lowercase(
        self,
    ):
        upper = TIP.upper()

        reader, _ = (
            self.make_reader(
                {
                    "/cryptarchia/info": {
                        "phase":
                            "Following",
                        "cryptarchia_info": {
                            "height": 1,
                            "tip": upper,
                        },
                    },
                }
            )
        )

        self.assertEqual(
            reader.read_node()[
                "tip"
            ],
            TIP,
        )

    def test_node_fetch_failure_is_unreachable(
        self,
    ):
        reader, _ = (
            self.make_reader(
                {
                    "/cryptarchia/info":
                        OSError(
                            "node down"
                        ),
                }
            )
        )

        self.assertEqual(
            reader.read_node(),
            {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
