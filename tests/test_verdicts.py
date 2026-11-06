"""End-to-end + unit tests for the differential scanner.

Run:  python -m pytest -q
No network, no API key required (every scan uses use_ai=False against the mock).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import decision
import similarity as sim
import engine
from models import Probe, UNAUTH, USER, ADMIN


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _scan(mock_api, tiers=None, **kw):
    _, spec_path = mock_api
    opts = dict(file_path=spec_path, output_file="/tmp/_pytest_out.csv",
                use_ai=False, verbose=False, max_retries=2,
                cooldown_cap=3.0, min_interval=0.0, tiers=tiers)
    opts.update(kw)
    verdicts = engine.run_scan(**opts)
    return {v.endpoint: v.category for v in verdicts}, verdicts


TIERS = {"user": [("Authorization", "Bearer user-token")],
         "admin": [("Authorization", "Bearer admin-token")]}


# --------------------------------------------------------------------------
# unit: similarity
# --------------------------------------------------------------------------
def test_similarity_identical_is_one():
    assert sim.similarity('{"a":1}', '{"a":1}') == 1.0

def test_similarity_drops_volatile_ids():
    a = '{"id":111,"name":"widget"}'
    b = '{"id":999,"name":"widget"}'
    assert sim.similarity(a, b) >= 0.9   # same resource, different id

def test_similarity_different_bodies_low():
    assert sim.similarity('{"a":1}', '{"totally":"different"}') < 0.6

def test_looks_sensitive():
    assert sim.looks_sensitive('{"email":"x@y.com"}')
    assert sim.looks_sensitive('key: sk-abcdef123456')
    assert not sim.looks_sensitive('{"status":"ok"}')


# --------------------------------------------------------------------------
# unit: decision matrix (pure, no HTTP)
# --------------------------------------------------------------------------
def _p(tier, status, body=""):
    return Probe(endpoint="/x", method="GET", params_values="{}", tier=tier,
                 status=status, body_len=len(body), body_norm=body, sample=body)

def test_decide_protected():
    v = decision.decide([_p(UNAUTH, 401)])
    assert v.category == "PROTECTED" and not v.signal

def test_decide_authz_bypass():
    probes = [_p(UNAUTH, 200, '{"a":1}'), _p(USER, 200, '{"a":1}')]
    v = decision.decide(probes, {"has_user": True})
    assert v.category == "AUTHZ-BYPASS" and v.signal

def test_bfla_requires_privileged_scope():
    # admin-scoped + unauth rejected + user==admin  -> BFLA
    probes = [_p(UNAUTH, 401), _p(USER, 200, '{"s":1}'), _p(ADMIN, 200, '{"s":1}')]
    v = decision.bfla_verdict(probes, {"has_user": True, "has_admin": True})
    assert v is None  # /x is not admin-scoped, so no BFLA
    # now with an admin-scoped endpoint
    for p in probes:
        p.endpoint = "/admin/leak"
    v = decision.bfla_verdict(probes, {"has_user": True, "has_admin": True})
    assert v and v.category == "BFLA-PRIVESC" and v.signal

def test_bfla_not_fired_for_self_service():
    # user==admin on a non-privileged path must NOT be a finding
    probes = [_p(UNAUTH, 401), _p(USER, 200, '{"u":"a"}'), _p(ADMIN, 200, '{"u":"a"}')]
    for p in probes:
        p.endpoint = "/me"
    assert decision.bfla_verdict(probes, {"has_user": True, "has_admin": True}) is None


# --------------------------------------------------------------------------
# end-to-end: tiered scan against the mock API
# --------------------------------------------------------------------------
def test_e2e_with_tiers(mock_api):
    by_ep, _ = _scan(mock_api, tiers=TIERS)
    assert by_ep["/me"] == "PROTECTED"
    assert by_ep["/admin/gated"] == "PROTECTED"
    assert by_ep["/open-sensitive"] == "AUTHZ-BYPASS"

def test_e2e_bfla_detected(mock_api):
    _, verdicts = _scan(mock_api, tiers=TIERS)
    cats = [v.category for v in verdicts if v.endpoint == "/admin/leak"]
    assert "BFLA-PRIVESC" in cats

def test_e2e_unauth_only_sensitive(mock_api):
    by_ep, _ = _scan(mock_api, tiers=None)
    assert by_ep["/open-sensitive"] == "OPEN-2XX-SENSITIVE"
    assert by_ep["/me"] == "PROTECTED"

def test_e2e_benign_public_is_review_not_sensitive(mock_api):
    # A 2xx with a non-sensitive body is surfaced for review, not flagged
    # as sensitive exposure.
    by_ep, _ = _scan(mock_api, tiers=None)
    assert by_ep["/public-same"] == "OPEN-2XX-REVIEW"


# --------------------------------------------------------------------------
# end-to-end: rate-limit behaviour
# --------------------------------------------------------------------------
def test_rate_limited_is_unverified_not_protected(mock_api):
    by_ep, _ = _scan(mock_api, tiers=None)
    assert by_ep["/always-limited"] == "UNVERIFIED-RATELIMITED"

def test_rate_limit_recovers(mock_api):
    # /recovers 429s twice then 200 -> after retries we get a real verdict,
    # never UNVERIFIED and never PROTECTED.
    by_ep, _ = _scan(mock_api, tiers=None)
    assert by_ep["/recovers"] in ("OPEN-2XX-REVIEW", "OPEN-2XX-SENSITIVE",
                                  "PUBLIC-LIKE")


# --------------------------------------------------------------------------
# reporting: signal-only findings file
# --------------------------------------------------------------------------
def test_findings_only_signal(mock_api, tmp_path):
    out = str(tmp_path / "scan")
    engine.run_scan(file_path=mock_api[1], output_file=out, use_ai=False,
                    verbose=False, tiers=TIERS, max_retries=1,
                    cooldown_cap=2.0, min_interval=0.0)
    findings = out + ".findings.csv"
    assert os.path.exists(findings)
    import csv
    with open(findings) as f:
        rows = list(csv.DictReader(f))
    # every written row must be a signal category
    assert all(r["category"] in
               ("AUTHZ-BYPASS", "BFLA-PRIVESC", "OPEN-2XX-SENSITIVE",
                "OPEN-2XX-REVIEW") for r in rows)
    # and no noise (protected / unverified) leaked into findings
    assert not any(r["category"] in ("PROTECTED", "UNVERIFIED-RATELIMITED")
                   for r in rows)
