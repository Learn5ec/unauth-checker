"""Unit tests for request assembly and header parsing (no network)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine import parse_header, build_request


# --------------------------------------------------------------------------
# parse_header
# --------------------------------------------------------------------------
def test_parse_full_header():
    assert parse_header("Authorization: Bearer abc") == ("Authorization", "Bearer abc")
    assert parse_header("X-API-Key: k1") == ("X-API-Key", "k1")
    assert parse_header("Cookie: a=1; b=2") == ("Cookie", "a=1; b=2")

def test_parse_bare_bearer_token():
    assert parse_header("Bearer xyz") == ("Authorization", "Bearer xyz")
    assert parse_header("Token abc") == ("Authorization", "Token abc")

def test_parse_bare_jwt_wrapped_as_bearer():
    assert parse_header("eyJhbGci.abc.def") == ("Authorization", "Bearer eyJhbGci.abc.def")

def test_parse_bare_cookie():
    assert parse_header("sid=9; theme=dark") == ("Cookie", "sid=9; theme=dark")

def test_parse_plain_token_default():
    assert parse_header("plainvalue") == ("Authorization", "Bearer plainvalue")


# --------------------------------------------------------------------------
# build_request
# --------------------------------------------------------------------------
BASE = "https://api.test/v1"

def _ep(path="/x", method="GET", params=None, request_body=None):
    return {"path": path, "method": method, "params": params or [],
            "request_body": request_body}


def test_path_param_substituted():
    ep = _ep(path="/orders/{id}/items", params=[{"name": "id", "in": "path"}])
    req = build_request(ep, {"id": "777"}, BASE)
    assert req["url"] == f"{BASE}/orders/777/items"
    assert req["has_unresolved_path"] is False

def test_path_param_filled_even_when_empty():
    # The empty param-set must still reach a concrete route, not a literal {}.
    ep = _ep(path="/orders/{id}", params=[{"name": "id", "in": "path"}])
    req = build_request(ep, {}, BASE)
    assert "{" not in req["url"]
    assert req["has_unresolved_path"] is False

def test_unresolved_placeholder_flagged():
    # A {token} in the path with no matching parameter definition stays literal.
    ep = _ep(path="/thing/{ghost}")
    req = build_request(ep, {}, BASE)
    assert req["has_unresolved_path"] is True

def test_query_param_respects_sample():
    ep = _ep(params=[{"name": "q", "in": "query"}])
    assert build_request(ep, {"q": "x"}, BASE)["params"] == {"q": "x"}
    assert build_request(ep, {}, BASE)["params"] == {}   # omitted in empty case

def test_header_and_cookie_routing():
    ep = _ep(params=[
        {"name": "X-Trace", "in": "header"},
        {"name": "sid", "in": "cookie"},
    ])
    req = build_request(ep, {"X-Trace": "t1", "sid": "9"}, BASE)
    assert req["headers"]["X-Trace"] == "t1"
    assert req["headers"]["Cookie"] == "sid=9"

def test_extra_headers_merged():
    req = build_request(_ep(), {}, BASE, extra_headers={"Authorization": "Bearer t"})
    assert req["headers"]["Authorization"] == "Bearer t"

def test_body_sent_for_post_only():
    body = {"content_type": "application/json", "value": {"a": 1}}
    post = build_request(_ep(method="POST", request_body=body), {}, BASE)
    assert post["json"] == {"a": 1}
    get = build_request(_ep(method="GET", request_body=body), {}, BASE)
    assert get["json"] is None

def test_path_value_url_encoded():
    ep = _ep(path="/f/{p}", params=[{"name": "p", "in": "path"}])
    req = build_request(ep, {"p": "a/b"}, BASE)
    assert "a%2Fb" in req["url"]
