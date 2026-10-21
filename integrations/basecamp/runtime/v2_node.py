#!/usr/bin/env python3

import json
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import (
    ProxyHandler,
    Request,
    build_opener,
)


DEFAULT_UPSTREAM = (
    "ht"
    "tp://127.0.0.1:8080"
)

TIP_RE = re.compile(
    r"^[0-9a-fA-F]{64}$"
)

DEFAULT_REWARDS_SNAPSHOT = Path(
    "/run/logos-observer-rewards/snapshot.json"
)


class LogosNodeReader:
    """
    Strict read-only mapper from the local Logos node API
    to the sanitized Observer v2 response contract.

    Raw upstream objects never leave this class.
    """

    def __init__(
        self,
        upstream=DEFAULT_UPSTREAM,
        *,
        timeout=4.0,
        cache_ttl=10.0,
        fetch_json=None,
        rewards_snapshot=DEFAULT_REWARDS_SNAPSHOT,
    ):
        self.upstream = (
            upstream.rstrip("/")
        )

        self.timeout = timeout
        self.cache_ttl = cache_ttl
        self.fetch_json = fetch_json
        self.rewards_snapshot = Path(
            rewards_snapshot
        )

        self._cache = {}
        self._cache_lock = threading.RLock()
        self._path_locks = {}

        # Never route the node's local API through HTTP_PROXY,
        # HTTPS_PROXY, or other environment proxy settings.
        #
        # Supplying an explicit empty ProxyHandler also prevents
        # urllib.build_opener() from installing its default
        # environment-aware proxy handler.
        self._opener = (
            build_opener(
                ProxyHandler({})
            )
            if fetch_json is None
            else None
        )

    def _request_json(self, path):
        if self.fetch_json is not None:
            return self.fetch_json(path)

        request = Request(
            self.upstream + path,
            method="GET",
            headers={
                "Accept":
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
                "upstream response is not an object"
            )

        return value

    def _path_lock(self, path):
        with self._cache_lock:
            lock = self._path_locks.get(
                path
            )

            if lock is None:
                lock = threading.Lock()

                self._path_locks[
                    path
                ] = lock

            return lock

    def _fetch(self, path):
        # Serialize only requests for the same upstream path.
        # Different node endpoints remain independently fetchable.
        with self._path_lock(path):
            now = time.monotonic()

            with self._cache_lock:
                cached = self._cache.get(
                    path
                )

            if cached is not None:
                cached_at, value = cached

                if (
                    now - cached_at
                    <= self.cache_ttl
                ):
                    return value

            value = self._request_json(
                path
            )

            with self._cache_lock:
                self._cache[path] = (
                    time.monotonic(),
                    value,
                )

            return value

    @staticmethod
    def _decimal_string(value):
        if (
            value is None
            or isinstance(value, bool)
        ):
            raise ValueError(
                "invalid decimal amount"
            )

        try:
            number = Decimal(
                str(value)
            )
        except (
            InvalidOperation,
            ValueError,
        ):
            raise ValueError(
                "invalid decimal amount"
            )

        return format(
            number,
            "f",
        )

    @staticmethod
    def _atomic_lgo_string(value):
        if isinstance(value, bool):
            raise ValueError(
                "invalid atomic LGO amount"
            )

        if isinstance(value, int):
            atoms = value
        elif (
            isinstance(value, str)
            and re.fullmatch(
                r"-?[0-9]+",
                value,
            )
        ):
            atoms = int(value)
        else:
            raise ValueError(
                "invalid atomic LGO amount"
            )

        number = (
            Decimal(atoms)
            / Decimal(1_000_000_000)
        )

        return (
            format(number, "f")
            .rstrip("0")
            .rstrip(".")
            or "0"
        )

    @staticmethod
    def _tip(value):
        if not isinstance(
            value,
            str,
        ):
            return None

        if not TIP_RE.fullmatch(
            value
        ):
            return None

        return value.lower()

    @staticmethod
    def _expiry_value(values):
        if not isinstance(
            values,
            list,
        ):
            raise ValueError(
                "slots_until_expiry is not an array"
            )

        if not values:
            return None

        parsed = []

        for value in values:
            if isinstance(
                value,
                bool,
            ):
                raise ValueError(
                    "invalid expiry value"
                )

            try:
                number = int(value)
            except (
                TypeError,
                ValueError,
            ):
                raise ValueError(
                    "invalid expiry value"
                )

            parsed.append(number)

        return min(parsed)

    def read_node(self):
        try:
            raw = self._fetch(
                "/cryptarchia/info"
            )
        except (
            OSError,
            URLError,
            ValueError,
            json.JSONDecodeError,
        ):
            return {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            }

        info = raw.get(
            "cryptarchia_info"
        )

        if not isinstance(
            info,
            dict,
        ):
            return {
                "reachable": False,
                "phase": None,
                "height": None,
                "tip": None,
            }

        phase = raw.get("phase")

        if not isinstance(
            phase,
            str,
        ):
            phase = None

        height = info.get(
            "height"
        )

        if (
            isinstance(height, bool)
            or not isinstance(
                height,
                int,
            )
        ):
            height = None

        return {
            "reachable": True,
            "phase": phase,
            "height": height,
            "tip": self._tip(
                info.get("tip")
            ),
        }

    def read_network(self):
        raw = self._fetch(
            "/network/info"
        )

        peers = raw.get(
            "n_peers"
        )

        if (
            isinstance(peers, bool)
            or not isinstance(
                peers,
                int,
            )
        ):
            raise ValueError(
                "invalid peer count"
            )

        return {
            "peers": peers,
        }

    def read_mining(self):
        raw = self._fetch(
            "/pow/status"
        )

        is_mining = raw.get(
            "is_mining"
        )

        rewards_enabled = raw.get(
            "are_rewards_enabled"
        )

        auto_claim = raw.get(
            "auto_claim"
        )

        if not isinstance(
            is_mining,
            bool,
        ):
            raise ValueError(
                "invalid mining state"
            )

        if not isinstance(
            rewards_enabled,
            bool,
        ):
            raise ValueError(
                "invalid rewards state"
            )

        if not isinstance(
            auto_claim,
            dict,
        ):
            raise ValueError(
                "invalid auto-claim state"
            )

        armed = auto_claim.get(
            "is_armed"
        )

        if not isinstance(
            armed,
            bool,
        ):
            raise ValueError(
                "invalid auto-claim state"
            )

        return {
            "is_mining":
                is_mining,
            "rewards_enabled":
                rewards_enabled,
            "auto_claim":
                armed,
        }

    def _read_rewards_snapshot(self):
        try:
            raw = json.loads(
                self.rewards_snapshot.read_text()
            )
        except (
            FileNotFoundError,
            PermissionError,
            OSError,
            json.JSONDecodeError,
        ):
            return None

        if not isinstance(raw, dict):
            return None

        collected_at = raw.get("collected_at")

        if (
            isinstance(collected_at, bool)
            or not isinstance(collected_at, int)
            or not 0 <= time.time() - collected_at <= 120
        ):
            return None

        mining_notes = raw.get(
            "mining_notes"
        )
        consensus = raw.get(
            "consensus"
        )

        if (
            isinstance(mining_notes, bool)
            or not isinstance(
                mining_notes,
                int,
            )
            or not isinstance(
                consensus,
                dict,
            )
        ):
            return None

        integer_fields = (
            "pow_eligible_notes",
            "pow_aging_notes",
            "wallet_eligible_notes",
        )

        parsed = {}

        for field in integer_fields:
            value = consensus.get(field)

            if (
                isinstance(value, bool)
                or not isinstance(
                    value,
                    int,
                )
            ):
                return None

            parsed[field] = value

        try:
            pow_balance = (
                self._atomic_lgo_string(
                    consensus.get(
                        "pow_eligible_balance_atoms"
                    )
                )
            )
            wallet_balance = (
                self._atomic_lgo_string(
                    consensus.get(
                        "wallet_eligible_balance_atoms"
                    )
                )
            )
        except ValueError:
            return None

        return {
            "mining_notes":
                mining_notes,
            "consensus": {
                "pow_eligible_notes":
                    parsed[
                        "pow_eligible_notes"
                    ],
                "pow_eligible_balance":
                    pow_balance,
                "pow_aging_notes":
                    parsed[
                        "pow_aging_notes"
                    ],
                "wallet_eligible_notes":
                    parsed[
                        "wallet_eligible_notes"
                    ],
                "wallet_eligible_balance":
                    wallet_balance,
            },
        }

    def read_rewards(self):
        pow_status = self._fetch(
            "/pow/status"
        )

        auto_claim = pow_status.get(
            "auto_claim"
        )

        if not isinstance(
            auto_claim,
            dict,
        ):
            raise ValueError(
                "invalid auto-claim state"
            )

        targets = auto_claim.get(
            "targets"
        )

        mining_balance = None

        if (
            isinstance(targets, list)
            and targets
            and isinstance(
                targets[0],
                dict,
            )
            and targets[0].get(
                "balance"
            ) is not None
        ):
            mining_balance = (
                self._atomic_lgo_string(
                    targets[0].get(
                        "balance"
                    )
                )
            )

        claimable = self._fetch(
            "/pow/rewards/claimable"
        )

        tickets = claimable.get(
            "claimable_tickets"
        )

        if (
            isinstance(tickets, bool)
            or not isinstance(
                tickets,
                int,
            )
        ):
            raise ValueError(
                "invalid claimable ticket count"
            )

        expiry = self._expiry_value(
            claimable.get(
                "slots_until_expiry"
            )
        )

        node = self.read_node()

        if not node.get(
            "reachable"
        ):
            raise RuntimeError(
                "node unavailable"
            )

        tip = node.get("tip")

        if tip is None:
            raise ValueError(
                "node tip unavailable"
            )

        query = urlencode(
            {
                "tip": tip,
            }
        )

        leader = self._fetch(
            "/leader/claim/vouchers?"
            + query
        )

        vouchers = leader.get(
            "vouchers"
        )

        if not isinstance(
            vouchers,
            list,
        ):
            raise ValueError(
                "invalid voucher list"
            )

        total_claimable = (
            self._decimal_string(
                leader.get(
                    "total_claimable"
                )
            )
        )

        result = {
            "mining_balance":
                mining_balance,
            "claimable_tickets":
                tickets,
            "slots_until_expiry":
                expiry,
            "vouchers":
                len(vouchers),
            "total_claimable":
                total_claimable,
        }

        snapshot = (
            self._read_rewards_snapshot()
        )

        if snapshot is not None:
            result.update(snapshot)

        return result

    def read_blend(self):
        raise RuntimeError(
            "blend.status.read is reserved"
        )
