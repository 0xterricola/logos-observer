#!/usr/bin/env python3

import base64
import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def spki_pin_from_public_key(public_key) -> str:
    spki_der = public_key.public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    digest = hashlib.sha256(spki_der).digest()

    return "sha256/" + b64url_encode(digest)


def spki_pin_from_certificate(cert: x509.Certificate) -> str:
    return spki_pin_from_public_key(
        cert.public_key()
    )


def load_certificate(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(
        path.read_bytes()
    )


def generate_p256_private_key():
    return ec.generate_private_key(
        ec.SECP256R1()
    )


def build_self_signed_certificate(
    private_key,
    *,
    common_name: str = "Logos Observer",
    dns_names=(),
    ip_addresses=(),
    now: datetime | None = None,
    lifetime_days: int = 3650,
):
    if now is None:
        now = datetime.now(timezone.utc)

    subject = issuer = x509.Name(
        [
            x509.NameAttribute(
                NameOID.COMMON_NAME,
                common_name,
            )
        ]
    )

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(
            x509.random_serial_number()
        )
        .not_valid_before(
            now - timedelta(minutes=5)
        )
        .not_valid_after(
            now + timedelta(days=lifetime_days)
        )
        .add_extension(
            x509.BasicConstraints(
                ca=False,
                path_length=None,
            ),
            critical=True,
        )
    )

    san_entries = []

    for name in dns_names:
        san_entries.append(
            x509.DNSName(name)
        )

    if ip_addresses:
        import ipaddress

        for address in ip_addresses:
            san_entries.append(
                x509.IPAddress(
                    ipaddress.ip_address(address)
                )
            )

    if san_entries:
        builder = builder.add_extension(
            x509.SubjectAlternativeName(
                san_entries
            ),
            critical=False,
        )

    return builder.sign(
        private_key=private_key,
        algorithm=hashes.SHA256(),
    )


def ensure_tls_identity(
    state_dir: Path,
    *,
    common_name: str = "Logos Observer",
    dns_names=(),
    ip_addresses=(),
):
    """
    Create the persistent Observer v2 TLS key/certificate if absent.

    The private key is long-lived. The SPKI pin therefore survives
    certificate renewal as long as this key is preserved.
    """

    state_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    key_path = state_dir / "observer-v2-key.pem"
    cert_path = state_dir / "observer-v2-cert.pem"

    if key_path.exists():
        private_key = serialization.load_pem_private_key(
            key_path.read_bytes(),
            password=None,
        )

        if not isinstance(
            private_key,
            ec.EllipticCurvePrivateKey,
        ):
            raise ValueError(
                "Observer TLS key is not an EC private key"
            )

        if not isinstance(
            private_key.curve,
            ec.SECP256R1,
        ):
            raise ValueError(
                "Observer TLS key is not P-256"
            )
    else:
        private_key = generate_p256_private_key()

        key_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )

        key_path.write_bytes(key_pem)
        os.chmod(key_path, 0o600)

    regenerate_cert = True

    if cert_path.exists():
        try:
            cert = load_certificate(cert_path)

            existing_spki = spki_pin_from_certificate(cert)
            current_spki = spki_pin_from_public_key(
                private_key.public_key()
            )

            if (
                existing_spki == current_spki
                and certificate_covers_names(
                    cert,
                    dns_names=dns_names,
                    ip_addresses=ip_addresses,
                )
            ):
                regenerate_cert = False
        except Exception:
            regenerate_cert = True

    if regenerate_cert:
        cert = build_self_signed_certificate(
            private_key,
            common_name=common_name,
            dns_names=dns_names,
            ip_addresses=ip_addresses,
        )

        cert_path.write_bytes(
            cert.public_bytes(
                serialization.Encoding.PEM
            )
        )

        os.chmod(cert_path, 0o644)
    else:
        cert = load_certificate(cert_path)

    return {
        "key_path": key_path,
        "cert_path": cert_path,
        "certificate": cert,
        "pin": spki_pin_from_certificate(cert),
    }


def create_server_ssl_context(
    cert_path: Path,
    key_path: Path,
):
    import ssl

    context = ssl.SSLContext(
        ssl.PROTOCOL_TLS_SERVER
    )

    context.minimum_version = (
        ssl.TLSVersion.TLSv1_3
    )
    context.maximum_version = (
        ssl.TLSVersion.TLSv1_3
    )

    context.load_cert_chain(
        certfile=str(cert_path),
        keyfile=str(key_path),
    )

    return context


def certificate_covers_names(
    certificate,
    *,
    dns_names=(),
    ip_addresses=(),
):
    try:
        san = certificate.extensions.get_extension_for_class(
            x509.SubjectAlternativeName
        ).value
    except x509.ExtensionNotFound:
        return not dns_names and not ip_addresses

    cert_dns = set(
        san.get_values_for_type(
            x509.DNSName
        )
    )

    cert_ips = {
        str(value)
        for value in san.get_values_for_type(
            x509.IPAddress
        )
    }

    return (
        set(dns_names).issubset(cert_dns)
        and set(ip_addresses).issubset(
            cert_ips
        )
    )
