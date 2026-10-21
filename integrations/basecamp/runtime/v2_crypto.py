#!/usr/bin/env python3

import base64
import hashlib
import hmac


V2_PROTOCOL = "LOGOS-OBSERVER-V2"


def b64url_encode(data: bytes) -> str:
    """RFC 4648 base64url without '=' padding."""
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def b64url_decode(text: str) -> bytes:
    """Decode RFC 4648 base64url with optional omitted padding."""
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def body_sha256_hex(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def canonical_request_v2(
    method: str,
    request_target: str,
    timestamp: str,
    nonce: str,
    device_id: str,
    body: bytes,
) -> bytes:
    """
    Build the frozen Logos Observer v2 canonical request.

    request_target must already be the exact request-target as sent:
      /path
      /path?query

    This function intentionally does not normalize, reorder, decode,
    re-encode, or otherwise modify request_target.
    """

    if not request_target.startswith("/"):
        raise ValueError("request target must begin with '/'")

    if "#" in request_target:
        raise ValueError("request target must not contain a fragment")

    if request_target.endswith("?"):
        raise ValueError("request target must not end with bare '?'")

    fields = (
        V2_PROTOCOL,
        method,
        request_target,
        timestamp,
        nonce,
        device_id,
        body_sha256_hex(body),
    )

    return "\n".join(fields).encode("utf-8")


def hmac_signature_v2(
    hmac_key: bytes,
    method: str,
    request_target: str,
    timestamp: str,
    nonce: str,
    device_id: str,
    body: bytes,
) -> str:
    canonical = canonical_request_v2(
        method,
        request_target,
        timestamp,
        nonce,
        device_id,
        body,
    )

    signature = hmac.new(
        hmac_key,
        canonical,
        hashlib.sha256,
    ).digest()

    return b64url_encode(signature)


def verify_hmac_signature_v2(
    hmac_key: bytes,
    supplied_signature: str,
    method: str,
    request_target: str,
    timestamp: str,
    nonce: str,
    device_id: str,
    body: bytes,
) -> bool:
    expected = hmac_signature_v2(
        hmac_key,
        method,
        request_target,
        timestamp,
        nonce,
        device_id,
        body,
    )

    return hmac.compare_digest(
        supplied_signature,
        expected,
    )
