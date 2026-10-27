"""ClickUp webhook signature check.

ClickUp signs every webhook request: X-Signature is the hex HMAC-SHA256 of
the raw request body, keyed with the secret returned when the webhook was
created (developer.clickup.com/docs/webhooksignature). Verify against the
raw bytes as received; re-serialising parsed JSON can change whitespace and
break the match.
"""
import hashlib
import hmac


def compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()


def is_valid_signature(secret: str, raw_body: bytes, header_value: str | None) -> bool:
    if not secret or not header_value:
        return False
    expected = compute_signature(secret, raw_body)
    return hmac.compare_digest(expected, header_value.strip().lower())
