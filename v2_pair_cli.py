#!/usr/bin/env python3

import argparse
import ipaddress
import shutil
import subprocess
from pathlib import Path

from v2_pairing import (
    PairingStore,
    V2_READ_SCOPES,
)
from v2_tls import ensure_tls_identity


def certificate_names_for_host(host):
    dns_names = [
        "logos-observer.local",
    ]
    ip_addresses = []

    try:
        ipaddress.ip_address(host)
    except ValueError:
        if host not in dns_names:
            dns_names.append(host)
    else:
        ip_addresses.append(host)

    return dns_names, ip_addresses


def endpoint_for_host(host, port):
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return f"{host}:{port}"

    if address.version == 6:
        return f"[{host}]:{port}"

    return f"{host}:{port}"


def create_local_pairing_offer(
    *,
    state_dir,
    advertise_host,
    port,
    display_name,
    scopes=V2_READ_SCOPES,
    bonjour=None,
    now=None,
):
    dns_names, ip_addresses = (
        certificate_names_for_host(
            advertise_host
        )
    )

    identity = ensure_tls_identity(
        Path(state_dir),
        common_name="Logos Observer",
        dns_names=dns_names,
        ip_addresses=ip_addresses,
    )

    store = PairingStore(
        Path(state_dir)
    )

    endpoint = endpoint_for_host(
        advertise_host,
        port,
    )

    offer = store.create_offer(
        host=endpoint,
        pin=identity["pin"],
        display_name=display_name,
        scopes=scopes,
        bonjour=bonjour,
        now=now,
    )

    return {
        **offer,
        "endpoint": endpoint,
        "pin": identity["pin"],
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Create a local-only Logos Observer "
            "v2 pairing offer."
        )
    )

    parser.add_argument(
        "--state-dir",
        type=Path,
        default=Path(".v2-state"),
    )

    parser.add_argument(
        "--host",
        required=True,
        help=(
            "address clients use to reach the "
            "Observer"
        ),
    )

    parser.add_argument(
        "--port",
        type=int,
        default=8081,
    )

    parser.add_argument(
        "--name",
        default="Logos Observer",
    )

    parser.add_argument(
        "--bonjour",
        default=(
            "Logos Observer."
            "_logos-observer._tcp"
        ),
    )

    parser.add_argument(
        "--scope",
        action="append",
        dest="scopes",
        choices=V2_READ_SCOPES,
        help=(
            "scope to offer; repeat for multiple. "
            "Defaults to all v2 read scopes."
        ),
    )

    parser.add_argument(
        "--no-terminal-qr",
        action="store_true",
        help=(
            "do not try to render with qrencode"
        ),
    )

    args = parser.parse_args()

    scopes = (
        tuple(args.scopes)
        if args.scopes
        else V2_READ_SCOPES
    )

    offer = create_local_pairing_offer(
        state_dir=args.state_dir,
        advertise_host=args.host,
        port=args.port,
        display_name=args.name,
        scopes=scopes,
        bonjour=args.bonjour,
    )

    print()
    print("Logos Observer v2 pairing offer")
    print(
        "Endpoint:",
        offer["endpoint"],
    )
    print(
        "SPKI pin:",
        offer["pin"],
    )
    print(
        "Expires:",
        offer["expires_at"],
    )
    print(
        "Scopes:",
        ", ".join(
            offer["offered_scopes"]
        ),
    )

    print()
    print("PAIRING URI")
    print(offer["qr"])
    print()

    if not args.no_terminal_qr:
        qrencode = shutil.which(
            "qrencode"
        )

        if qrencode:
            subprocess.run(
                [
                    qrencode,
                    "-t",
                    "ANSIUTF8",
                    offer["qr"],
                ],
                check=False,
            )
        else:
            print(
                "qrencode not installed; "
                "pairing URI printed above."
            )


if __name__ == "__main__":
    main()
