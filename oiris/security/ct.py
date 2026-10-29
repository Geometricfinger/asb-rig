"""Constant-time comparison. Never compare secrets with ==. Python cannot guarantee
timing of surrounding high-level code; this is a stated limit."""
import hmac


def equal(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)
