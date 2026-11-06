"""Shared dataclasses for authorization-tiered scanning.

Kept in one place so `engine` (which produces Probes) and `decision` (which
consumes them into a Verdict) share a single contract.
"""

from dataclasses import dataclass, field
from typing import Optional


# Tier names
UNAUTH = "unauth"
USER = "user"
ADMIN = "admin"

# Status sentinels (non-integer) recorded on a Probe.
RATE_LIMITED = "RATE-LIMITED"
ERROR = "ERROR"


@dataclass
class Probe:
    """A single HTTP request made at one authorization tier for one param-set."""
    endpoint: str
    method: str
    params_values: str          # canonical JSON string of the param set used
    tier: str                   # UNAUTH | USER | ADMIN
    status: object              # int HTTP code, or RATE_LIMITED / ERROR sentinel
    body_len: int = 0
    body_norm: str = ""         # normalized body (see similarity.normalize)
    sample: str = ""            # truncated raw body, for the trace only
    headers: dict = field(default_factory=dict)
    error: Optional[str] = None
    attempt: int = 0            # retry attempts consumed (rate-limit engine)

    @property
    def ok(self) -> bool:
        return isinstance(self.status, int) and 200 <= self.status < 300

    @property
    def protected(self) -> bool:
        return self.status in (401, 403)

    @property
    def unverified(self) -> bool:
        return self.status == RATE_LIMITED


@dataclass
class Verdict:
    """The cross-tier conclusion for one (endpoint, method, param-set)."""
    endpoint: str
    method: str
    params_values: str
    category: str
    confidence: int
    level: str
    signal: bool
    evidence: str
    tiers: dict = field(default_factory=dict)   # {"unauth":200,"user":200,...}
    similarity: Optional[float] = None          # relevant body-similarity, if any
