import json
import unittest

from v2_chat import BasecampChatReader


class BasecampChatReaderTests(
    unittest.TestCase
):
    def test_bridge_must_be_loopback(self):
        allowed = [
            "http://127.0.0.1:8645/rpc",
            "http://localhost:8645/rpc",
            "http://[::1]:8645/rpc",
        ]

        for upstream in allowed:
            BasecampChatReader(
                upstream=upstream
            )

        rejected = [
            "http://192.168.1.10:8645/rpc",
            "http://example.com:8645/rpc",
            "ftp://127.0.0.1:8645/rpc",
            (
                "http://user:pass@"
                "127.0.0.1:8645/rpc"
            ),
        ]

        for upstream in rejected:
            with self.assertRaises(
                ValueError
            ):
                BasecampChatReader(
                    upstream=upstream
                )

    def test_json_rpc_envelope_validation(self):
        class FakeResponse:
            def __init__(self, payload):
                self.data = json.dumps(
                    payload
                ).encode("utf-8")

            def __enter__(self):
                return self

            def __exit__(
                self,
                exc_type,
                exc,
                traceback,
            ):
                return False

            def read(self):
                return self.data

        class FakeOpener:
            def __init__(self, payload):
                self.payload = payload

            def open(
                self,
                request,
                timeout,
            ):
                return FakeResponse(
                    self.payload
                )

        reader = BasecampChatReader()
        reader._opener = FakeOpener(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "result": "abc123",
            }
        )

        self.assertEqual(
            reader._call(
                "get_address"
            ),
            "abc123",
        )

        invalid = [
            {
                "jsonrpc": "1.0",
                "id": 1,
                "result": "abc123",
            },
            {
                "jsonrpc": "2.0",
                "id": 2,
                "result": "abc123",
            },
            {
                "jsonrpc": "2.0",
                "id": True,
                "result": "abc123",
            },
        ]

        for payload in invalid:
            reader = BasecampChatReader()
            reader._opener = FakeOpener(
                payload
            )

            with self.assertRaises(
                ValueError
            ):
                reader._call(
                    "get_address"
                )

    def test_chat_not_started(self):
        def rpc_call(method, params):
            self.assertEqual(
                method,
                "get_address",
            )
            return ""

        reader = BasecampChatReader(
            rpc_call=rpc_call
        )

        self.assertEqual(
            reader.read_conversations(),
            {
                "available": False,
                "reason":
                    "chat_not_started",
            },
        )

    def test_conversations(self):
        def rpc_call(method, params):
            if method == "get_address":
                return "abc123"

            if method == "list_conversations":
                return [
                    {
                        "convo_id": "c1",
                        "kind": "direct",
                        "message_count": 2,
                        "last_activity_ms": 200,
                        "preview": "gm",
                        "history_only": False,
                    }
                ]

            raise AssertionError(method)

        reader = BasecampChatReader(
            rpc_call=rpc_call
        )

        self.assertEqual(
            reader.read_conversations(),
            {
                "available": True,
                "conversations": [
                    {
                        "convo_id": "c1",
                        "kind": "direct",
                        "message_count": 2,
                        "last_activity_ms": 200,
                        "preview": "gm",
                        "history_only": False,
                    }
                ],
            },
        )

    def test_messages_since_oldest_first(self):
        def rpc_call(method, params):
            if method == "get_address":
                return "abc123"

            if method == "get_messages":
                self.assertEqual(
                    params,
                    {
                        "convo_id": "c1",
                    },
                )

                return [
                    {
                        "from_self": False,
                        "content": "new",
                        "timestamp_ms": 300,
                        "sender": "peer",
                    },
                    {
                        "from_self": True,
                        "content": "mine",
                        "timestamp_ms": 200,
                    },
                    {
                        "from_self": False,
                        "content": "old",
                        "timestamp_ms": 100,
                        "sender": "peer",
                    },
                ]

            raise AssertionError(method)

        reader = BasecampChatReader(
            rpc_call=rpc_call
        )

        self.assertEqual(
            reader.read_messages(
                "c1",
                since_ms=100,
            ),
            {
                "available": True,
                "convo_id": "c1",
                "messages": [
                    {
                        "content": "mine",
                        "from_self": True,
                        "timestamp_ms": 200,
                    },
                    {
                        "content": "new",
                        "from_self": False,
                        "timestamp_ms": 300,
                        "sender": "peer",
                    },
                ],
            },
        )


if __name__ == "__main__":
    unittest.main()
