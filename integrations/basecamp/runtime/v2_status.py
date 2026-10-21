#!/usr/bin/env python3

from datetime import datetime, timezone


SECTION_SCOPES = {
    "node": "node.status.read",
    "network": "network.status.read",
    "mining": "mining.status.read",
    "rewards": "rewards.status.read",
    "blend": "blend.status.read",
}


def observed_at_iso(now=None):
    if now is None:
        now = datetime.now(timezone.utc)

    if isinstance(now, (int, float)):
        now = datetime.fromtimestamp(
            now,
            tz=timezone.utc,
        )

    return (
        now.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def build_status_snapshot(
    *,
    device,
    reader,
    now=None,
):
    """
    Build the frozen Observer v2 combined status response.

    Rules:
      - ungranted section: omitted
      - granted section read failure: null
      - node unreachable: HTTP layer still returns 200;
        node.reachable=false and every other granted
        section is null
    """

    granted = set(
        device.get("scopes", [])
    )

    result = {
        "v": 2,
        "observed_at":
            observed_at_iso(now),
    }

    node_granted = (
        SECTION_SCOPES["node"]
        in granted
    )

    node = None

    if node_granted:
        try:
            node = reader.read_node()
        except Exception:
            node = {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            }

        if not isinstance(node, dict):
            node = {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            }

        reachable = (
            node.get("reachable")
            is True
        )

        if not reachable:
            node = {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            }

        result["node"] = node

        if not reachable:
            for section, scope in (
                SECTION_SCOPES.items()
            ):
                if section == "node":
                    continue

                if scope in granted:
                    result[section] = None

            return result

    readers = {
        "network":
            reader.read_network,
        "mining":
            reader.read_mining,
        "rewards":
            reader.read_rewards,
    }

    # Blend is reserved in v2 until its exact
    # underlying node route is frozen.
    if (
        SECTION_SCOPES["blend"]
        in granted
    ):
        readers["blend"] = (
            reader.read_blend
        )

    for section, read in (
        readers.items()
    ):
        scope = SECTION_SCOPES[
            section
        ]

        if scope not in granted:
            continue

        try:
            value = read()
        except Exception:
            value = None

        result[section] = value

    return result


class UnavailableStatusReader:
    """
    Safe default for the standalone reference server before
    a real Logos upstream is configured.
    """

    def read_node(self):
        return {
            "reachable": False,
            "phase": None,
            "height": None,
            "tip": None,
        }

    def read_network(self):
        raise RuntimeError(
            "node unavailable"
        )

    def read_mining(self):
        raise RuntimeError(
            "node unavailable"
        )

    def read_rewards(self):
        raise RuntimeError(
            "node unavailable"
        )

    def read_blend(self):
        raise RuntimeError(
            "blend route not configured"
        )
