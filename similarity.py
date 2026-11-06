"""Body normalization & similarity for cross-tier response comparison.

Used to decide whether an unauthenticated response carries the *same* data as an
authenticated one (auth bypass) or whether a normal-user response matches an
admin response (privilege escalation). Volatile fields (ids, timestamps) are
stripped so identical resources still compare as equal.
"""

import re
import json
import difflib

_MAX_LEN = 50_000

# Substrings that mark a JSON key as volatile (values change per-request/record
# even when the resource is the same).
_VOLATILE_KEYS = (
    "id", "uuid", "guid", "timestamp", "time", "date",
    "createdat", "updatedat", "requestid", "traceid", "nonce", "token",
)

# Long digit / hex runs collapse to '#' so order-123 ≈ order-456 in non-JSON text.
_DIGIT_RUN = re.compile(r"\d{2,}")
_HEX_RUN = re.compile(r"[0-9a-fA-F]{16,}")

_SENSITIVE_RES = [
    re.compile(r"[^@\s]+@[^@\s]+\.[A-Za-z]{2,}"),          # email
    re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+"),  # JWT
    re.compile(r"\b(sk-|xox[baprs]-|AIza|AKIA|ghp_)[A-Za-z0-9_-]{6,}"),  # api keys
    re.compile(r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b"),        # SSN-ish
]


def _drop_volatile(obj):
    if isinstance(obj, dict):
        return {
            k: _drop_volatile(v)
            for k, v in obj.items()
            if not any(sub in str(k).lower() for sub in _VOLATILE_KEYS)
        }
    if isinstance(obj, list):
        return [_drop_volatile(v) for v in obj]
    return obj


def normalize(text):
    """Normalize a response body for comparison (JSON-aware, volatile fields
    dropped, digit/hex runs collapsed). Never raises."""
    if not text:
        return ""
    text = str(text)[:_MAX_LEN]
    try:
        parsed = json.loads(text)
        parsed = _drop_volatile(parsed)
        return json.dumps(parsed, sort_keys=True, separators=(",", ":"))
    except Exception:
        pass
    text = text.strip()[:_MAX_LEN]
    text = _HEX_RUN.sub("#", text)
    text = _DIGIT_RUN.sub("#", text)
    return text


def similarity(a, b):
    """Sequence similarity in [0,1] between two (normalized) bodies."""
    na, nb = normalize(a), normalize(b)
    if not na and not nb:
        return 0.0
    if na == nb:
        return 1.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def looks_sensitive(text):
    """True if the body appears to contain secrets or PII."""
    if not text:
        return False
    sample = str(text)[:_MAX_LEN]
    return any(rx.search(sample) for rx in _SENSITIVE_RES)
