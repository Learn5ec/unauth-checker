"""Smart rate-limit management for unauth-checker.

Reads rate-limit metadata from responses at runtime, paces requests to stay
under the advertised cap, and — when a limit is hit — reads the cooldown hint,
waits, then re-runs the throttled request so the final results are accurate.

The single entry point is `SafeHTTP`, a thin wrapper around `requests` that
every probe should fire through.
"""

import time
import random
from urllib.parse import urlparse
from email.utils import parsedate_to_datetime

import requests

# Statuses that mean "your request did not get a real answer, try again later".
RETRY_STATUSES = {429, 503}
# Sentinel recorded on a probe whose retries were exhausted by rate limiting.
RATE_LIMITED = "RATE-LIMITED"


class RateLimitedExhausted(Exception):
    """Raised when a request kept getting throttled past the retry budget."""


def parse_retry_after(value):
    """Parse a Retry-After header -> seconds to wait (float) or None.

    Handles both delta-seconds ("120") and HTTP-date formats.
    """
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        # Compare in epoch seconds to avoid tz issues.
        delta = dt.timestamp() - time.time()
        return max(0.0, delta)
    except Exception:
        return None


def _first(header, *names):
    for n in names:
        v = header.get(n)
        if v is not None and str(v).strip() != "":
            return str(v).strip()
    return None


def _norm_reset(raw_reset):
    """Normalize a Reset header to 'seconds from now', resolving the
    epoch-vs-delta ambiguity (GitHub uses epoch, Cloudflare uses delta)."""
    if raw_reset is None:
        return None
    try:
        v = float(raw_reset)
    except (TypeError, ValueError):
        return None
    if v > 1_000_000_000:  # looks like an absolute epoch timestamp
        return max(0.0, v - time.time())
    return max(0.0, v)  # already a delta in seconds


def _parse_draft_ratelimit(value):
    """Parse the IETF draft header, e.g. `RateLimit: "acct";r=149;t=47`.

    Returns (remaining, reset_in) using the last bucket described.
    """
    remaining = reset_in = None
    for bucket in value.split(","):
        params = {}
        for part in bucket.split(";"):
            part = part.strip()
            if "=" in part:
                k, _, v = part.partition("=")
                params[k.strip().lower()] = v.strip().strip('"')
        if "r" in params:
            try:
                remaining = float(params["r"])
            except ValueError:
                pass
        if "t" in params:
            try:
                reset_in = float(params["t"])
            except ValueError:
                pass
    return remaining, reset_in


def parse_rate_headers(header):
    """Extract a normalized view of any advertised rate limit from headers.

    Returns a dict with optional keys: limit, remaining, reset_in (seconds),
    retry_after (seconds). Missing fields are simply absent.
    """
    out = {}

    limit = _first(header, "RateLimit-Limit", "X-RateLimit-Limit")
    if limit is not None:
        try:
            out["limit"] = float(limit)
        except ValueError:
            pass

    remaining = _first(header, "RateLimit-Remaining", "X-RateLimit-Remaining")
    reset_in = _first(header, "RateLimit-Reset", "X-RateLimit-Reset")

    if remaining is None and reset_in is None:
        # IETF draft combined header: RateLimit: "acct";r=..;t=..
        draft = header.get("RateLimit")
        if draft:
            remaining, reset_in = _parse_draft_ratelimit(draft)

    if remaining is not None:
        try:
            out["remaining"] = float(remaining)
        except ValueError:
            pass

    normalized = _norm_reset(reset_in)
    if normalized is not None:
        out["reset_in"] = normalized

    retry_after = parse_retry_after(header.get("Retry-After"))
    if retry_after is not None:
        out["retry_after"] = retry_after

    return out


class _HostState:
    __slots__ = ("interval", "reset_ts")

    def __init__(self, interval):
        self.interval = interval   # current min seconds between requests
        self.reset_ts = 0.0        # wall-clock when the current window resets


class SafeHTTP:
    """requests wrapper with adaptive pacing + cooldown-and-retry.

    - Passive limit reading: every response's headers update per-host state.
    - Pacing: sleeps before each request to stay under the observed/advertised
      cap; AIMD (additive-increase / multiplicative-decrease) when the API does
      not advertise a limit.
    - On 429/503 (or a Retry-After hint): sleeps the cooldown then re-runs the
      same request, up to max_retries. Exhaustion raises RateLimitedExhausted.
    """

    def __init__(self, max_rps=5.0, min_interval=0.05, rate_margin=2,
                 max_retries=4, cooldown_cap=120.0, adaptive=True,
                 respect_retry_after=True, jitter=0.0, session=None):
        self.session = session or requests.Session()
        self.max_rps = max(0.1, float(max_rps))
        self.min_interval = max(0.0, float(min_interval))
        self.rate_margin = max(0, int(rate_margin))
        self.max_retries = max(0, int(max_retries))
        self.cooldown_cap = float(cooldown_cap)
        self.adaptive = adaptive
        self.respect_retry_after = respect_retry_after
        self.jitter = max(0.0, float(jitter))
        self.default_interval = 1.0 / self.max_rps
        self._hosts = {}
        # Cumulative observability counters (surfaced by the reporter).
        self.throttle_hits = 0
        self.retries_done = 0
        self.unverified = 0

    def _state(self, host):
        st = self._hosts.get(host)
        if st is None:
            st = _HostState(self.default_interval)
            self._hosts[host] = st
        return st

    def _acquire(self, host):
        """Sleep so we don't fire faster than the host tolerates."""
        st = self._state(host)
        wait = st.interval
        # If we know a window reset in the near future and it is sooner than our
        # normal interval, hold until then.
        if st.reset_ts and st.reset_ts > time.monotonic():
            wait = max(wait, st.reset_ts - time.monotonic())
        if wait > 0:
            if self.jitter:
                wait += random.uniform(0, self.jitter)
            time.sleep(wait)

    def _observe(self, host, response):
        """Feed a (non-throttled) response's headers back into host state."""
        st = self._state(host)
        info = parse_rate_headers(response.headers)

        if "reset_in" in info:
            st.reset_ts = time.monotonic() + info["reset_in"]

        if not self.adaptive:
            st.interval = self.default_interval
            return

        if "remaining" in info and "reset_in" in info and info["remaining"] is not None:
            window = max(1.0, info.get("reset_in", 1.0))
            usable = max(1.0, info["remaining"] - self.rate_margin)
            st.interval = min(self.default_interval, window / usable)
            st.interval = max(self.min_interval, st.interval)
        else:
            # No advertised limit -> additive increase (speed up), floored.
            st.interval = max(self.min_interval, st.interval * 0.95)

    def _backoff(self, attempt):
        return min(self.cooldown_cap, self.default_interval * (2 ** attempt))

    def request(self, method, url, **kwargs):
        host = urlparse(url).netloc
        attempts = 0
        while True:
            self._acquire(host)
            try:
                resp = self.session.request(method, url, **kwargs)
            except requests.RequestException:
                # Transport errors are not rate limits; surface as before.
                raise

            info = parse_rate_headers(resp.headers)
            throttled = resp.status_code in RETRY_STATUSES or (
                "retry_after" in info and resp.status_code >= 500
            )

            if not throttled:
                self._observe(host, resp)
                return resp

            self.throttle_hits += 1
            if attempts >= self.max_retries:
                self.unverified += 1
                raise RateLimitedExhausted(
                    f"{method} {url}: rate-limited after {attempts} retries"
                )

            # Cooldown: prefer explicit hint, then window reset, then backoff.
            wait = info.get("retry_after")
            if wait is None:
                st = self._state(host)
                wait = info.get("reset_in") or self._backoff(attempts)
                if "retry_after" not in info and info.get("reset_in") is None:
                    st.interval = min(self.cooldown_cap, max(st.interval, wait))

            if wait > self.cooldown_cap and not self.respect_retry_after:
                wait = self.cooldown_cap

            time.sleep(wait + (random.uniform(0, self.jitter) if self.jitter else 0))
            attempts += 1
            self.retries_done += 1

    # Convenience passthroughs mirroring the requests API used by the engine.
    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def close(self):
        try:
            self.session.close()
        except Exception:
            pass
