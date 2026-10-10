#!/usr/bin/env python3

import json
import os
import re
import subprocess
import time
from pathlib import Path


LOGOSCTL = "logosctl"
KEYSTORE = Path(
    "/var/lib/logos-node/keystore.yaml"
)
SNAPSHOT = Path(
    "/run/logos-observer-rewards/snapshot.json"
)

LOGOS_ENV = {
    **os.environ,
    "HOME": "/var/lib/logos-node",
    "LOGOSCTL_CONFIG_DIR":
        "/var/lib/logos-node/.logosctl",
}


def _call(method, *args):
    result = subprocess.run(
        [
            LOGOSCTL,
            "call",
            "blockchain_module",
            method,
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=4,
        env=LOGOS_ENV,
    )

    envelope = json.loads(
        result.stdout
    )

    if envelope.get("success") is False:
        raise RuntimeError(
            f"{method} failed: {envelope.get('error')}"
        )

    result = envelope.get("result", envelope)

    if not isinstance(result, dict):
        raise ValueError(
            f"invalid {method} response"
        )

    value = result.get("value")

    if isinstance(value, str):
        value = json.loads(value)

    if not isinstance(value, dict):
        raise ValueError(
            f"invalid {method} response"
        )

    return value


def _pow_claim_key():
    text = KEYSTORE.read_text()

    match = re.search(
        r"^\s*PoWClaim:\s+(\S+)",
        text,
        re.MULTILINE,
    )

    if not match:
        raise ValueError(
            "PoWClaim key unavailable"
        )

    value = match.group(1)

    if value == "!Zk":
        raise ValueError(
            "PoWClaim key unavailable"
        )

    return value


def _integer(value):
    if isinstance(value, bool):
        raise ValueError(
            "invalid note value"
        )

    return int(value)


def collect():
    pow_notes = _call(
        "wallet_get_notes",
        _pow_claim_key(),
        "",
    )

    leader_notes = _call(
        "wallet_get_leader_aged_notes",
        "",
    )

    pow_items = pow_notes.get(
        "notes",
        [],
    )
    leader_items = leader_notes.get(
        "notes",
        [],
    )

    if not isinstance(pow_items, list):
        raise ValueError(
            "invalid PoW notes"
        )

    if not isinstance(
        leader_items,
        list,
    ):
        raise ValueError(
            "invalid leader-aged notes"
        )

    leader_by_id = {
        item.get("id"): item
        for item in leader_items
        if isinstance(item, dict)
        and isinstance(
            item.get("id"),
            str,
        )
    }

    eligible = []

    for item in pow_items:
        if not isinstance(item, dict):
            raise ValueError(
                "invalid PoW note"
            )

        note_id = item.get("id")

        if note_id in leader_by_id:
            eligible.append(
                leader_by_id[note_id]
            )

    pow_total = len(pow_items)
    pow_eligible = len(eligible)

    return {
        "mining_notes":
            pow_total,
        "consensus": {
            "pow_eligible_notes":
                pow_eligible,
            "pow_eligible_balance_atoms":
                str(
                    sum(
                        _integer(
                            item.get("value")
                        )
                        for item
                        in eligible
                    )
                ),
            "pow_aging_notes":
                pow_total
                - pow_eligible,
            "wallet_eligible_notes":
                len(leader_items),
            "wallet_eligible_balance_atoms":
                str(
                    _integer(
                        leader_notes.get(
                            "total_value",
                            0,
                        )
                    )
                ),
        },
    }


def write_snapshot(data):
    SNAPSHOT.parent.mkdir(
        mode=0o750,
        parents=True,
        exist_ok=True,
    )

    temp = SNAPSHOT.with_suffix(
        ".tmp"
    )

    temp.write_text(
        json.dumps(
            data,
            separators=(",", ":"),
        )
        + "\n"
    )

    os.chmod(temp, 0o640)

    temp.replace(SNAPSHOT)


def main():
    data = collect()
    data["collected_at"] = int(time.time())
    write_snapshot(data)


if __name__ == "__main__":
    main()
