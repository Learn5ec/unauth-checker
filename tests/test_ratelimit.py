"""Unit tests for the rate-limit engine (no network, no real sleeps).

Covers the pure parsers plus SafeHTTP's pacing / cooldown / exhaustion logic by
driving it with a stub requests.Session.
"""

import os
import sys
import time
from email.utils import formatdate

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import ratelimit
from ratelimit import (
    SafeHTTP, RateLimitedExhausted,
    parse_retry_after, parse_rate_headers, _norm_reset,
)


# --------------------------------------------------------------------------
# parse_retry_after
# --------------------------------------------------------------------------
def test_retry_after_seconds():
    assert parse_retry_after("120") == 120.0
    assert parse_retry_after("0") == 0.0

def test_retry_after_http_date():
    future = formatdate(time.time() + 120, usegmt=True)
    got = parse_retry_after(future)
    assert got is not None and 110 < got < 130

def test_retry_after_garbage_is_none():
    assert parse_retry_after(None) is None
    assert parse_retry_after("") is None
    assert parse_retry_after("not-a-number") is None


# --------------------------------------------------------------------------
# _norm_reset (epoch vs delta)
# --------------------------------------------------------------------------
def test_norm_reset_delta_vs_epoch():
    assert _norm_reset("30") == 30.0                 # small -> treated as delta
    epoch = time.time() + 300
    assert 290 < _norm_reset(str(epoch)) < 310       # large -> epoch, converted
    assert _norm_reset(None) is None


# --------------------------------------------------------------------------
# parse_rate_headers
# --------------------------------------------------------------------------
def test_parse_x_ratelimit_delta():
    h = {"X-RateLimit-Limit": "100",
         "X-RateLimit-Remaining": "10",
         "X-RateLimit-Reset": "30"}
    out = parse_rate_headers(h)
    assert out["limit"] == 100.0
    assert out["remaining"] == 10.0
    assert out["reset_in"] == 30.0

def test_parse_ietf_draft_combined():
    # RateLimit: "acct";r=149;t=47   ->   remaining=149, reset_in=47
    out = parse_rate_headers({"RateLimit": '"acct";r=149;t=47'})
    assert out["remaining"] == 149.0
    assert out["reset_in"] == 47.0

def test_parse_retry_after_merged_in():
    out = parse_rate_headers({"Retry-After": "5"})
    assert out["retry_after"] == 5.0


# --------------------------------------------------------------------------
# SafeHTTP — stub session, no real sleeps
# --------------------------------------------------------------------------
class FakeResp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}

class FakeSession:
    """Returns a scripted sequence of responses (repeats the last one)."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def request(self, method, url, **kw):
        i = min(self.calls, len(self.responses) - 1)
        self.calls += 1
        r = self.responses[i]
        if isinstance(r, Exception):
            raise r
        return r

    def close(self):
        pass


def _patch_sleep(monkeypatch):
    waits = []
    monkeypatch.setattr(ratelimit.time, "sleep", lambda s: waits.append(s))
    return waits


def test_exhaustion_raises_and_counts(monkeypatch):
    waits = _patch_sleep(monkeypatch)
    sess = FakeSession([FakeResp(429, {"Retry-After": "1"})])  # always throttled
    http = SafeHTTP(min_interval=0.0, max_retries=2, session=sess)
    with pytest.raises(RateLimitedExhausted):
        http.get("http://x/y")
    assert http.throttle_hits == 3      # initial + 2 retries all throttled
    assert http.retries_done == 2
    assert http.unverified == 1
    assert [w for w in waits if w >= 1.0] == [1.0, 1.0]  # honoured Retry-After each time


def test_recovery_after_throttle(monkeypatch):
    _patch_sleep(monkeypatch)
    sess = FakeSession([
        FakeResp(429, {"Retry-After": "1"}),
        FakeResp(429, {"Retry-After": "1"}),
        FakeResp(200, {}),
    ])
    http = SafeHTTP(min_interval=0.0, max_retries=4, session=sess)
    resp = http.get("http://x/y")
    assert resp.status_code == 200
    assert http.retries_done == 2
    assert http.unverified == 0


def test_observe_speeds_up_from_advertised_headroom():
    # Huge remaining over a short window -> pacer may go faster than the default.
    sess = FakeSession([FakeResp(200, {
        "X-RateLimit-Remaining": "100000",
        "X-RateLimit-Reset": "1",
    })])
    http = SafeHTTP(max_rps=1000, min_interval=0.0, session=sess)
    default = http.default_interval
    http.get("http://x/y")
    st = http._state("x")
    assert st.interval < default  # adapted downward


def test_adaptive_increase_without_headers():
    sess = FakeSession([FakeResp(200, {})])
    http = SafeHTTP(min_interval=0.0, session=sess)
    st = http._state("x")
    st.interval = 1.0
    http.get("http://x/y")          # no limit headers -> multiplicative decrease
    assert http._state("x").interval == 0.95
