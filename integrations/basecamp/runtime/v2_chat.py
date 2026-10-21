#!/usr/bin/env python3

import json
from ipaddress import ip_address
from urllib.parse import urlsplit
from urllib.request import (
    ProxyHandler,
    Request,
    build_opener,
)


DEFAULT_CHAT_BRIDGE = "http://127.0.0.1:8645/rpc"
MAX_MESSAGES = 500


def _validate_loopback_bridge(upstream):
    if not isinstance(upstream, str):
        raise ValueError(
            "chat bridge URL must be a string"
        )

    parsed = urlsplit(upstream)

    if parsed.scheme not in (
        "http",
        "https",
    ):
        raise ValueError(
            "chat bridge URL must use HTTP or HTTPS"
        )

    if parsed.hostname is None:
        raise ValueError(
            "chat bridge URL has no host"
        )

    if (
        parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError(
            "chat bridge URL must not contain credentials"
        )

    if parsed.fragment:
        raise ValueError(
            "chat bridge URL must not contain a fragment"
        )

    host = parsed.hostname

    if host.lower() != "localhost":
        try:
            address = ip_address(host)
        except ValueError as exc:
            raise ValueError(
                "chat bridge must use a loopback host"
            ) from exc

        if not address.is_loopback:
            raise ValueError(
                "chat bridge must use a loopback host"
            )

    return upstream


class BasecampChatReader:
    """
    Strict read-only adapter from the local Basecamp JSON-RPC bridge
    to the Observer v2 Chat response contract.

    This class never exposes Chat write methods and never handles
    Chat keys. The bridge is expected to remain bound to loopback.
    """

    def __init__(
        self,
        upstream=DEFAULT_CHAT_BRIDGE,
        *,
        timeout=4.0,
        rpc_call=None,
    ):
        self.upstream = (
            _validate_loopback_bridge(
                upstream
            )
        )
        self.timeout = timeout
        self.rpc_call = rpc_call
        self._next_id = 1

        # Never route the local Basecamp bridge through HTTP_PROXY,
        # HTTPS_PROXY, or other environment proxy settings.
        self._opener = (
            build_opener(
                ProxyHandler({})
            )
            if rpc_call is None
            else None
        )

    def _call(self, method, params=None):
        if self.rpc_call is not None:
            return self.rpc_call(
                method,
                params,
            )

        request_id = self._next_id
        self._next_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": (
                "chat_module."
                + method
            ),
        }

        if params is not None:
            payload["params"] = params

        body = json.dumps(
            payload,
            separators=(",", ":"),
        ).encode("utf-8")

        request = Request(
            self.upstream,
            data=body,
            method="POST",
            headers={
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
            },
        )

        with self._opener.open(
            request,
            timeout=self.timeout,
        ) as response:
            data = response.read()

        value = json.loads(
            data.decode("utf-8")
        )

        if not isinstance(value, dict):
            raise ValueError(
                "bridge response is not an object"
            )

        if value.get("jsonrpc") != "2.0":
            raise ValueError(
                "bridge response has invalid JSON-RPC version"
            )

        response_id = value.get("id")

        if (
            type(response_id) is not int
            or response_id != request_id
        ):
            raise ValueError(
                "bridge response has mismatched id"
            )

        if "error" in value:
            raise ValueError(
                "bridge returned JSON-RPC error"
            )

        if "result" not in value:
            raise ValueError(
                "bridge response has no result"
            )

        return value["result"]

    def _available(self):
        address = self._call(
            "get_address"
        )

        return (
            isinstance(address, str)
            and bool(address)
        )

    @staticmethod
    def _unavailable():
        return {
            "available": False,
            "reason": "chat_not_started",
        }

    def read_conversations(self):
        if not self._available():
            return self._unavailable()

        conversations = self._call(
            "list_conversations"
        )

        if not isinstance(
            conversations,
            list,
        ):
            raise ValueError(
                "conversation result is not an array"
            )

        result = []

        for conversation in conversations:
            if not isinstance(
                conversation,
                dict,
            ):
                raise ValueError(
                    "conversation is not an object"
                )

            convo_id = conversation.get(
                "convo_id"
            )

            if not isinstance(
                convo_id,
                str,
            ) or not convo_id:
                raise ValueError(
                    "conversation has invalid convo_id"
                )

            item = {
                "convo_id": convo_id,
            }

            for key in (
                "nickname",
                "message_count",
                "last_activity_ms",
                "kind",
                "name",
                "description",
                "preview",
                "history_only",
            ):
                if key in conversation:
                    item[key] = (
                        conversation[key]
                    )

            result.append(item)

        return {
            "available": True,
            "conversations": result,
        }

    def read_messages(
        self,
        convo_id,
        *,
        since_ms=None,
    ):
        if not self._available():
            return self._unavailable()

        if not isinstance(
            convo_id,
            str,
        ) or not convo_id:
            raise ValueError(
                "invalid convo_id"
            )

        messages = self._call(
            "get_messages",
            {
                "convo_id":
                    convo_id,
            },
        )

        if not isinstance(
            messages,
            list,
        ):
            raise ValueError(
                "message result is not an array"
            )

        result = []

        for message in messages:
            if not isinstance(
                message,
                dict,
            ):
                raise ValueError(
                    "message is not an object"
                )

            content = message.get(
                "content"
            )
            timestamp_ms = message.get(
                "timestamp_ms"
            )
            from_self = message.get(
                "from_self"
            )

            if not isinstance(
                content,
                str,
            ):
                raise ValueError(
                    "message content is invalid"
                )

            if (
                isinstance(timestamp_ms, bool)
                or not isinstance(
                    timestamp_ms,
                    int,
                )
            ):
                raise ValueError(
                    "message timestamp is invalid"
                )

            if not isinstance(
                from_self,
                bool,
            ):
                raise ValueError(
                    "message from_self is invalid"
                )

            if (
                since_ms is not None
                and timestamp_ms <= since_ms
            ):
                continue

            item = {
                "content": content,
                "from_self": from_self,
                "timestamp_ms":
                    timestamp_ms,
            }

            if not from_self:
                sender = message.get(
                    "sender"
                )

                if isinstance(
                    sender,
                    str,
                ) and sender:
                    item["sender"] = sender

            result.append(item)

        result.sort(
            key=lambda item:
                item["timestamp_ms"]
        )

        if since_ms is None:
            result = result[-MAX_MESSAGES:]

        return {
            "available": True,
            "convo_id": convo_id,
            "messages": result,
        }
