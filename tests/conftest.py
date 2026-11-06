"""Shared fixtures: a throwaway multi-tier mock API for end-to-end scans.

The server encodes the exact scenarios the decision matrix must distinguish, so
a passing end-to-end test means the *whole* pipeline (probe -> normalize ->
decide -> report) agrees, not just one unit in isolation.
"""

import json
import threading
import socketserver
import http.server

import pytest


class _Handler(http.server.BaseHTTPRequestHandler):
    # Per-path hit counters so we can simulate rate-limit-then-recover.
    counts = {}

    def log_message(self, *a):
        pass

    def _send(self, code, body, headers=None):
        raw = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(raw)

    def _role(self):
        auth = self.headers.get("Authorization", "")
        if "admin" in auth:
            return "admin"
        if "user" in auth:
            return "user"
        return "none"

    def do_GET(self):
        role = self._role()
        path = self.path.split("?")[0]
        handler = getattr(self, "route_" + path.strip("/").replace("/", "_").replace("-", "_"), None)
        if handler:
            return handler(role)
        self._send(404, {"error": "not found"})

    # ---- scenarios ----------------------------------------------------
    def route_me(self, role):                      # self-service: NOT BFLA
        if role == "none":
            return self._send(401, {"error": "unauthorized"})
        self._send(200, {"user": "alice"})

    def route_admin_leak(self, role):              # genuine BFLA
        if role == "none":
            return self._send(401, {"error": "unauthorized"})
        self._send(200, {"secret": 42})            # user sees admin data

    def route_admin_gated(self, role):             # correctly gated
        if role == "none":
            return self._send(401, {"error": "unauthorized"})
        if role == "user":
            return self._send(403, {"error": "forbidden"})
        self._send(200, {"admin": True})

    def route_open_sensitive(self, role):          # open, sensitive body
        self._send(200, {"email": "a@b.com", "apikey": "sk-abc123"})

    def route_public_same(self, role):             # open, benign body
        self._send(200, {"status": "ok"})

    def route_always_limited(self, role):          # never lets us through
        self._send(429, {"error": "slow down"},
                   headers={"Retry-After": "1"})

    def route_recovers(self, role):                # 429 then 200
        n = _Handler.counts.get("recovers", 0) + 1
        _Handler.counts["recovers"] = n
        if n <= 2:
            self._send(429, {"error": "slow down"},
                       headers={"Retry-After": "1"})
        else:
            self._send(200, {"now": "available"})


class _Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


@pytest.fixture
def mock_api():
    """Start the mock API; yield (base_url, spec_path)."""
    _Handler.counts = {}
    srv = _Server(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    base = f"http://127.0.0.1:{port}"
    spec = {
        "openapi": "3.0.0",
        "info": {"title": "mock", "version": "1"},
        "servers": [{"url": base}],
        "paths": {
            "/me": {"get": {}},
            "/admin/leak": {"get": {}},
            "/admin/gated": {"get": {}},
            "/open-sensitive": {"get": {}},
            "/public-same": {"get": {}},
            "/always-limited": {"get": {}},
            "/recovers": {"get": {}},
        },
    }
    import tempfile, os
    fd, spec_path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w") as f:
        json.dump(spec, f)
    try:
        yield base, spec_path
    finally:
        srv.shutdown()
