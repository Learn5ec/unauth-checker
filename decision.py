"""Cross-tier decision matrix.

Consumes the `Probe` objects (one per active authorization tier) gathered for a
single (endpoint, method, param-set) and produces a `Verdict`. The point of the
whole tool lives here: a finding is a COMPARISON across tiers, and a response
is only trusted once it is not rate-limited.
"""

from models import Probe, Verdict, UNAUTH, USER, ADMIN, RATE_LIMITED, ERROR
import similarity as sim

_DEFAULTS = {
    "sim_strong": 0.90,   # bodies considered "the same data"
    "sim_shape": 0.60,    # bodies same shape (both non-trivial collections)
    "has_user": False,    # a --user-header was configured
    "has_admin": False,   # an --admin-header was configured
}


def _tier(probes, name):
    for p in probes:
        if p.tier == name:
            return p
    return None


def _levels(score):
    if score >= 80:
        return "High"
    if score >= 50:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Inconclusive"


def _similarity(a, b):
    if a is None or b is None:
        return None
    return sim.similarity(getattr(a, "body_norm", "") or "",
                          getattr(b, "body_norm", "") or "")


def decide(probes, opts=None):
    opts = {**_DEFAULTS, **(opts or {})}
    sim_strong = opts["sim_strong"]
    sim_shape = opts["sim_shape"]
    has_user = opts["has_user"]
    has_admin = opts["has_admin"]

    u = _tier(probes, UNAUTH)
    us = _tier(probes, USER)
    ad = _tier(probes, ADMIN)

    tiers_seen = {p.tier: p.status for p in probes}
    endpoint = probes[0].endpoint if probes else ""
    method = probes[0].method if probes else ""
    params_values = probes[0].params_values if probes else "{}"

    def V(category, confidence, signal, evidence, simval=None):
        return Verdict(
            endpoint=endpoint, method=method, params_values=params_values,
            category=category, confidence=confidence, level=_levels(confidence),
            signal=signal, evidence=evidence, tiers=tiers_seen, similarity=simval,
        )

    # Transport / unverified states first — never scored as a finding.
    if u is None:
        return V("ERROR", 0, False, "no unauthenticated probe was made")
    if u.status == RATE_LIMITED:
        return V("UNVERIFIED-RATELIMITED", 0, False,
                 "unauth request rate-limited; retries exhausted")
    if u.status == ERROR:
        return V("ERROR", 0, False, "unauth request error")

    # Protected / non-data states.
    if u.status in (401, 403):
        return V("PROTECTED", 0, False, f"unauth {u.status} (auth enforced)")
    if 300 <= u.status < 400:
        return V("REDIRECT-LOGIN", 10, False, f"unauth {u.status} redirect")
    if 500 <= u.status < 600:
        return V("SERVER-ERROR", 15, False, f"unauth {u.status}")
    if 400 <= u.status < 500:
        return V("REACHABLE-NO-DATA", 10, False, f"unauth {u.status}")

    # From here: unauth got a 2xx — the interesting part.
    if u.ok:
        # Differential with user tier -> authentication bypass.
        if has_user and us is not None and us.ok:
            su = _similarity(u, us)
            if su is not None and su >= sim_strong:
                return V("AUTHZ-BYPASS", 90, True,
                         f"unauth {u.status} == user {us.status} (sim {su:.2f})", su)
            if su is not None and su < sim_shape:
                # Auth genuinely changes the response -> likely intended gating.
                return V("PUBLIC-LIKE", 20, False,
                         f"unauth {u.status} differs from user {us.status} (sim {su:.2f})", su)
            # In-between: surface for review.
            return V("OPEN-2XX-REVIEW", 55, True,
                     f"unauth {u.status} vs user {us.status} (sim {su:.2f})", su)

        # With an admin tier but no user comparison possible (BFLA needs a user
        # baseline); still, admin==user handled below when user present.

        # No auth headers configured: single-tier 2xx.
        if not has_user:
            if sim.looks_sensitive(getattr(u, "sample", "") or getattr(u, "body_norm", "")):
                return V("OPEN-2XX-SENSITIVE", 80, True, "unauth 2xx with sensitive-looking body")
            return V("OPEN-2XX-REVIEW", 55, True,
                     f"unauth {u.status} — verify this is meant to be public")

        # has_user but user did not return 2xx (e.g. user got non-2xx):
        return V("OPEN-2XX-REVIEW", 55, True,
                 f"unauth {u.status} but user {us.status if us else 'n/a'}")

    # Fallback.
    return V("ERROR", 0, False, f"unhandled unauth status {u.status}")


def bfla_verdict(probes, opts=None):
    """Separate privilege-escalation check across user vs admin tiers.

    Returned as an additional Verdict when a normal user reaches admin-level
    data. Kept distinct so a single endpoint can report BOTH an auth-bypass and
    a priv-esc angle if applicable.
    """
    opts = {**_DEFAULTS, **(opts or {})}
    us = _tier(probes, USER)
    ad = _tier(probes, ADMIN)
    if not (us and ad and us.ok and ad.ok):
        return None
    s = _similarity(us, ad)
    if s is not None and s >= opts["sim_strong"]:
        return Verdict(
            endpoint=us.endpoint, method=us.method, params_values=us.params_values,
            category="BFLA-PRIVESC", confidence=88, level=_levels(88), signal=True,
            evidence=f"user {us.status} == admin {ad.status} (sim {s:.2f})",
            tiers={p.tier: p.status for p in probes}, similarity=s,
        )
    return None
