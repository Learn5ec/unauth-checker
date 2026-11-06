import json
import csv
import sys
import os
import re
import requests
from urllib.parse import urlparse, quote
from typing import Dict, Any, List, Tuple, Optional
from ai_agent import AIAgent
from ratelimit import SafeHTTP, RateLimitedExhausted
from models import Probe, UNAUTH, USER, ADMIN, RATE_LIMITED, ERROR
import decision
import reporting

# Try to import openpyxl for Excel generation, make it optional
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, Alignment, PatternFill
    from openpyxl.utils import get_column_letter
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

# Lazy initialization to avoid import-time failures
_agent: Optional[AIAgent] = None

def get_agent() -> AIAgent:
    global _agent
    if _agent is None:
        _agent = AIAgent()
    return _agent

CSV_FIELDS = [
    "endpoint",
    "method",
    "params_count",
    "params_values",
    "status_codes",
    "response",
    "confidence",
    "confidence_level",
    "notes"
]

# -------------------------------------------------
# Progress Bar
# -------------------------------------------------

def update_progress(current: int, total: int):
    bar_len = 25
    filled = int(bar_len * current / total)
    bar = "█" * filled + "-" * (bar_len - filled)
    sys.stdout.write(f"\rProgress: [{bar}] {current} / {total} endpoints evaluated")
    sys.stdout.flush()

# -------------------------------------------------
# Excel Helpers (Formatted output)
# -------------------------------------------------

# Column width mappings (in cm, converted to Excel units)
# Excel column width: 1 cm ≈ 3.78 characters
COLUMN_WIDTHS_CM = {
    "endpoint": 4.7,        # 3.2 + 1.5
    "method": 2.5,          # 1.0 + 1.5
    "params_count": 3.55,   # 3.4 + 0.15
    "params_values": 5.0,   # 3.5 + 1.5
    "status_codes": 3.25,   # 3.0 + 0.25
    "response": 11.5,       # 10.0 + 1.5
    "confidence": 2.9,      # 2.5 + 0.4
    "confidence_level": 4.2, # 3.5 + 0.7
    "notes": 5.5            # 4.0 + 1.5
}

# Convert cm to Excel units (1 cm = 3.78 Excel units approximately)
COLUMN_WIDTHS = {k: v * 3.78 for k, v in COLUMN_WIDTHS_CM.items()}

# Row heights (in cm, converted to points)
# Excel row height: 1 cm = 28.35 points
HEADER_ROW_HEIGHT_CM = 0.7
DATA_ROW_HEIGHT_CM = 3.85
HEADER_ROW_HEIGHT_POINTS = HEADER_ROW_HEIGHT_CM * 28.35
DATA_ROW_HEIGHT_POINTS = DATA_ROW_HEIGHT_CM * 28.35

# Alignment configuration
CENTER_ALIGNED_COLUMNS = {"method", "params_count", "status_codes", "confidence", "confidence_level"}
TOP_ALIGNED_COLUMNS = {"response"}

_excel_workbook = None
_excel_worksheet = None
_excel_filename = None

def init_excel_file(filename: str):
    """Initialize Excel file with headers and formatting."""
    global _excel_workbook, _excel_worksheet, _excel_filename
    
    if not OPENPYXL_AVAILABLE:
        return
    
    try:
        excel_filename = filename.replace('.csv', '.xlsx')
        _excel_filename = excel_filename
        
        _excel_workbook = Workbook()
        _excel_worksheet = _excel_workbook.active
        _excel_worksheet.title = "Unauth Check Results"
        
        # Write headers with proper alignment
        for col_idx, field in enumerate(CSV_FIELDS, 1):
            cell = _excel_worksheet.cell(row=1, column=col_idx)
            cell.value = field
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            
            # Apply alignment based on column type (title row is top-aligned vertically)
            # "response" and "notes" are center-aligned in title row, rest keep their alignment
            if field in {"response", "notes"}:
                cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            elif field in CENTER_ALIGNED_COLUMNS:
                cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
            else:
                cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
        
        # Set column widths (in Excel units, converted from cm)
        for col_idx, field in enumerate(CSV_FIELDS, 1):
            width = COLUMN_WIDTHS.get(field, 15)
            _excel_worksheet.column_dimensions[get_column_letter(col_idx)].width = width
        
        # Set header row height (in points, converted from cm)
        _excel_worksheet.row_dimensions[1].height = HEADER_ROW_HEIGHT_POINTS
        
    except Exception as e:
        print(f"\n[!] Warning: Failed to initialize Excel file: {e}", file=sys.stderr)
        _excel_workbook = None
        _excel_worksheet = None

def append_excel_row(row: Dict[str, Any]):
    """Append a row to the Excel file and save in real-time."""
    global _excel_worksheet, _excel_workbook, _excel_filename
    
    if not OPENPYXL_AVAILABLE or _excel_worksheet is None:
        return
    
    try:
        row_num = _excel_worksheet.max_row + 1
        
        # Set row height for data rows (in points, converted from cm)
        _excel_worksheet.row_dimensions[row_num].height = DATA_ROW_HEIGHT_POINTS
        
        for col_idx, field in enumerate(CSV_FIELDS, 1):
            cell = _excel_worksheet.cell(row=row_num, column=col_idx)
            value = row.get(field, "")
            cell.value = str(value)[:5000] if len(str(value)) > 5000 else value  # Limit to 5000 chars for Excel
            
            # Apply alignment based on column type
            if field in TOP_ALIGNED_COLUMNS:
                # Top-aligned (response column)
                if field in CENTER_ALIGNED_COLUMNS:
                    cell.alignment = Alignment(horizontal="center", vertical="top", wrap_text=True)
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            elif field in CENTER_ALIGNED_COLUMNS:
                # Center-aligned, vertically centered
                cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            else:
                # Left-aligned, vertically centered
                cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        
        # Save Excel file in real-time after each row (like CSV)
        if _excel_filename and _excel_workbook:
            _excel_workbook.save(_excel_filename)
        
    except Exception as e:
        print(f"\n[!] Warning: Failed to write Excel row: {e}", file=sys.stderr)

def save_excel_file():
    """Save and close the Excel file."""
    global _excel_workbook, _excel_worksheet, _excel_filename
    
    if not OPENPYXL_AVAILABLE or _excel_workbook is None:
        return
    
    try:
        if _excel_filename:
            _excel_workbook.save(_excel_filename)
            _excel_workbook.close()
    except Exception as e:
        print(f"\n[!] Warning: Failed to save Excel file: {e}", file=sys.stderr)
    finally:
        _excel_workbook = None
        _excel_worksheet = None
        _excel_filename = None

# -------------------------------------------------
# CSV Helpers (Resume-safe)
# -------------------------------------------------

def write_csv_header_if_needed(filename: str):
    if not os.path.exists(filename):
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
            
            # Initialize Excel file if available
            init_excel_file(filename)
        except Exception as e:
            raise ValueError(f"Failed to create CSV file {filename}: {e}")

def append_csv_row(filename: str, row: Dict[str, Any]):
    try:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerow(row)
        
        # Also append to Excel file if available
        append_excel_row(row)
    except Exception as e:
        # Log error but don't crash - allow scan to continue
        print(f"\n[!] Warning: Failed to write CSV row: {e}", file=sys.stderr)

def load_completed_endpoints(filename: str) -> set:
    completed = set()
    if not os.path.exists(filename):
        return completed

    try:
        with open(filename, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Include params_values in key to track all 3 test cases
                key = f"{row['method']} {row['endpoint']} {row.get('params_values', '')}"
                completed.add(key)
    except Exception as e:
        # If we can't read the file, assume no endpoints are completed
        # This allows the scan to continue even if CSV is corrupted
        return completed

    return completed

# -------------------------------------------------
# OpenAPI Loading
# -------------------------------------------------

def extract_base_url_from_spec(spec: Dict) -> str:
    """Extract base URL from OpenAPI spec's servers field."""
    # OpenAPI 3.0+ uses 'servers' array
    servers = spec.get("servers", [])
    if servers and isinstance(servers, list) and len(servers) > 0:
        server_url = servers[0].get("url", "") if isinstance(servers[0], dict) else str(servers[0])
        if server_url:
            # Remove trailing slash if present
            return server_url.rstrip("/")
    
    # OpenAPI 2.0 uses 'host', 'basePath', 'schemes'
    host = spec.get("host", "")
    base_path = spec.get("basePath", "")
    schemes = spec.get("schemes", ["https"])
    scheme = schemes[0] if schemes else "https"
    
    if host:
        base_url = f"{scheme}://{host}{base_path}".rstrip("/")
        return base_url
    
    return ""

def load_openapi(url: str = None, file_path: str = None) -> Tuple[Dict, str]:
    spec = None
    
    if url:
        try:
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            spec = r.json()
            # Try to extract from spec first, fallback to URL base
            base_url = extract_base_url_from_spec(spec)
            if not base_url:
                base_url = r.url.rsplit("/", 1)[0]
            return spec, base_url
        except requests.RequestException as e:
            raise ValueError(f"Failed to fetch OpenAPI spec from URL: {e}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in OpenAPI spec: {e}")

    if file_path:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                spec = json.load(f)
        except FileNotFoundError:
            raise ValueError(f"OpenAPI file not found: {file_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in OpenAPI file: {e}")
        except Exception as e:
            raise ValueError(f"Error reading OpenAPI file: {e}")
        
        base_url = extract_base_url_from_spec(spec)
        if not base_url:
            raise ValueError(
                "No base URL found in OpenAPI spec. "
                "Please provide 'servers' (OpenAPI 3.0+) or 'host' (OpenAPI 2.0) in the spec, "
                "or use --url instead of --file."
            )
        return spec, base_url

    raise ValueError("No OpenAPI source provided")

# -------------------------------------------------
# Endpoint Extraction
# -------------------------------------------------

def extract_request_body(details: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull a concrete example/default from an operation's requestBody.

    Returns {"content_type": ..., "value": <python value>} or None. Uses the
    spec's own example/default (no AI), preferring application/json.
    """
    body = details.get("requestBody")
    if not isinstance(body, dict):
        return None
    content = body.get("content", {})
    if not isinstance(content, dict) or not content:
        return None
    # Prefer application/json, else first available media type.
    ctype = next((c for c in content if "json" in c.lower()), next(iter(content), None))
    if ctype is None:
        return None
    media = content.get(ctype, {})
    if not isinstance(media, dict):
        return None
    value = None
    if "example" in media:
        value = media["example"]
    else:
        schema = media.get("schema", {})
        if isinstance(schema, dict):
            value = schema.get("example", schema.get("default"))
    if value is None:
        return None
    return {"content_type": ctype, "value": value}


def extract_endpoints(spec: Dict) -> List[Dict[str, Any]]:
    endpoints = []

    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, details in methods.items():
            if not isinstance(details, dict):
                continue
            if method.lower() not in ("get", "post", "put", "delete", "patch", "head", "options"):
                continue

            params = []
            for p in details.get("parameters", []):
                if not isinstance(p, dict):
                    continue
                schema = p.get("schema", {}) if isinstance(p.get("schema"), dict) else {}
                params.append({
                    "name": p.get("name"),
                    "in": p.get("in", ""),
                    "type": schema.get("type", p.get("type", "string")),
                    "description": p.get("description", ""),
                    "example": schema.get("example", p.get("example")),
                    "default": schema.get("default", p.get("default")),
                    "enum": schema.get("enum", p.get("enum")),
                })

            endpoints.append({
                "path": path,
                "method": method.upper(),
                "params": params,
                "request_body": extract_request_body(details),
            })

    return endpoints

# -------------------------------------------------
# Sample Generation (AI or heuristic, Max 2 sets)
# -------------------------------------------------

# Type-based fallback values used when AI generation is skipped or fails.
# Also used as the sole source of samples under --skip-ai-params.
TYPE_FALLBACK = {
    "integer": "1",
    "number": "1.0",
    "boolean": "true",
    "string": "test",
    "array": "[]",
    "object": "{}",
}

def heuristic_value(p: Dict[str, Any]) -> str:
    """Derive a sample value from the OpenAPI spec alone (no AI call)."""
    for key in ("example", "default"):
        if p.get(key) not in (None, ""):
            return str(p[key])
    if p.get("enum"):
        return str(p["enum"][0])
    return TYPE_FALLBACK.get(p.get("type", "string"), "test")

def generate_param_samples(endpoint: Dict[str, Any], use_ai: bool = True) -> List[Dict[str, str]]:
    """Build up to 2 parameter sets to exercise an endpoint.

    When use_ai is False (i.e. --skip-ai-params), no AI/agent call is made at
    all; values come from the spec (example/default/enum) or type-based
    fallbacks, so no API key of any kind is required.
    """
    if not endpoint["params"]:
        # Parameterless endpoint: only the empty test case applies. Returning []
        # (rather than [{}]) avoids sending the empty request a second time as a
        # duplicate "set_1" case.
        return []

    if not use_ai:
        return [{p["name"]: heuristic_value(p) for p in endpoint["params"]}]

    agent = get_agent()
    samples = []
    for _ in range(2):
        sample = {}
        for p in endpoint["params"]:
            value = agent.generate_sample_value(p["type"], p["name"], p["description"])
            # If the model failed and returned the placeholder, fall back to the spec.
            if value == "test":
                value = heuristic_value(p)
            sample[p["name"]] = value
        samples.append(sample)

    return samples

# -------------------------------------------------
# Response Body Cleaner
# -------------------------------------------------

def clean_response_body(text: str, limit: int = 500) -> str:
    if not text:
        return "<empty response>"

    text = text.strip()

    try:
        parsed = json.loads(text)
        pretty = json.dumps(parsed, indent=2)
        result = pretty[:limit]
    except Exception:
        result = text[:limit]
    
    # Replace newlines with spaces for CSV compatibility (CSV writer will handle quotes)
    # But keep it readable - we'll let csv.DictWriter handle proper escaping
    return result

# -------------------------------------------------
# Endpoint Testing
# -------------------------------------------------

def format_params_values(params: Dict[str, str]) -> str:
    """Format params dict as JSON string for CSV."""
    if not params:
        return "{}"
    return json.dumps(params, sort_keys=True)

# Response statuses that indicate the endpoint is clearly protected / not
# reachable without auth — these are scored as Inconclusive regardless of body.
PROTECTED_STATUSES = {401, 403}

def _level_for(score: int) -> str:
    if score >= 80:
        return "High"
    if score >= 50:
        return "Medium"
    if score >= 20:
        return "Low"
    return "Inconclusive"

def score_result(statuses: set, response_body: str) -> "tuple[int, str]":
    """Grade a single test-case result into (confidence, level).

    Mirrors the README bands (80-100 High, 50-79 Medium, 20-49 Low, 0-19
    Inconclusive) instead of the previous 0-or-60-only behaviour.
    """
    if "ERROR" in statuses or not statuses:
        return 0, "Inconclusive"

    # A single request yields one status; take the most informative one.
    code = max(statuses) if isinstance(next(iter(statuses)), int) else 0

    # Explicitly protected -> no unauth access demonstrated.
    if code in PROTECTED_STATUSES:
        return 0, "Inconclusive"

    # 2xx with a real payload -> strong indication of unauthenticated access.
    if 200 <= code < 300:
        body = (response_body or "").strip()
        if not body or body == "<empty response>":
            return 45, _level_for(45)  # reachable but returned nothing useful
        return 85, _level_for(85)

    # Server error -> endpoint is reachable pre-auth (handler ran) but failed.
    if 500 <= code < 600:
        return 35, _level_for(35)

    # Redirects often bounce to a login page -> weak signal.
    if 300 <= code < 400:
        return 25, _level_for(25)

    # 404 / other 4xx -> inconclusive.
    return 10, _level_for(10)

# -------------------------------------------------
# Request Building (path/query/header/body routing)
# -------------------------------------------------

BODY_METHODS = {"POST", "PUT", "PATCH"}

def build_request(endpoint, sample, base_url, extra_headers=None, send_body=True):
    """Assemble method/url/query/headers/body for one probe, routing each
    parameter to its OpenAPI `in` location.

    - path params are substituted into the URL (always filled, even in the
      empty case, so the request reaches the concrete route instead of a
      literal `/…/{id}/…`).
    - query params respect the sample (omitted in the empty case).
    - header / cookie params are sent as headers.
    - requestBody example/default is sent as a JSON body for POST/PUT/PATCH.
    """
    base = base_url.rstrip("/")
    path = endpoint["path"]
    if not path.startswith("/"):
        path = "/" + path

    query = {}
    headers = dict(extra_headers or {})
    cookie_parts = []

    for p in endpoint["params"]:
        name = p.get("name")
        if not name:
            continue
        loc = (p.get("in") or "").lower()
        value = sample.get(name) if sample else None

        if loc == "path":
            # Always substitute path params; fall back to the spec value so the
            # concrete route is reachable.
            if value is None:
                value = heuristic_value(p)
            path = path.replace("{" + str(name) + "}", quote(str(value), safe=""))
        elif value is None:
            continue
        elif loc == "query":
            query[name] = value
        elif loc == "header":
            headers[name] = value
        elif loc == "cookie":
            cookie_parts.append(f"{name}={value}")

    if cookie_parts:
        existing = headers.get("Cookie", "")
        headers["Cookie"] = "; ".join(([existing] if existing else []) + cookie_parts)

    # Any unsubstituted {placeholders} left? Signal so callers can mark the probe
    # unreliable rather than treating a literal-brace 4xx as "protected".
    has_unresolved = "{" in path and "}" in path

    # requestBody example/default is independent of the query-param sample:
    # send it whenever the method takes a body and the spec provides one.
    body_json = None
    if send_body and endpoint.get("method") in BODY_METHODS and endpoint.get("request_body"):
        body_json = endpoint["request_body"]["value"]

    return {
        "method": endpoint["method"],
        "url": f"{base}{path}",
        "params": query,
        "headers": headers,
        "json": body_json,
        "has_unresolved_path": has_unresolved,
    }

# -------------------------------------------------
# Header parsing (authorization tiers)
# -------------------------------------------------

def parse_header(s: str):
    """Parse a -x/-a header value into (name, value).

    Supports a full `Name: value` form and bare tokens/cookies:
      - "Authorization: Bearer eyJ…" / "Cookie: a=1;b=2" / "X-API-Key: k" -> as-is
      - bare "eyJ…" / "Bearer …" / "Token …" / token -> Authorization: Bearer <v>
      - value containing '=' and ';' -> Cookie: <v>
    """
    s = (s or "").strip()
    if ":" in s:
        name, _, value = s.partition(":")
        name = name.strip()
        value = value.strip()
        if name and value:
            return name, value
    # Bare-value fallbacks.
    if s[:7].lower() == "bearer " or s[:6].lower() == "token ":
        return "Authorization", s
    if s.startswith("eyJ") or ("=" in s and ";" in s):
        if "=" in s and ";" in s:
            return "Cookie", s
        return "Authorization", "Bearer " + s
    return "Authorization", "Bearer " + s


def _probe_once(endpoint, params, base_url, tier, params_str, headers, http, verbose):
    """Fire a single request at one tier and return a Probe (never raises)."""
    probe = Probe(endpoint["path"], endpoint["method"], params_str, tier, status=ERROR)
    try:
        req = build_request(endpoint, params, base_url, extra_headers=headers or None)
        sender = http or requests
        r = sender.request(
            req["method"], req["url"],
            params=req["params"] or None,
            headers=req["headers"] or None,
            json=req["json"],
            timeout=10,
        )
        probe.status = r.status_code
        text = r.text or ""
        probe.body_len = len(text)
        probe.body_norm = text[:50000]
        probe.sample = clean_response_body(text, limit=1000)
        probe.headers = dict(r.headers)
        if req["has_unresolved_path"] and verbose:
            print("        [!] Unresolved path placeholder in URL — result may be unreliable")
        if verbose:
            print(f"        → [{tier}] {r.status_code} ({len(text)}B)")
    except RateLimitedExhausted as e:
        probe.status = RATE_LIMITED
        probe.error = str(e)
        if verbose:
            print(f"        → [{tier}] rate-limited (retries exhausted)")
    except requests.RequestException as e:
        probe.status = ERROR
        probe.error = str(e)
        if verbose:
            print(f"        → [{tier}] ERROR: {e}")
    return probe


def probe_endpoint(endpoint, base_url, samples, active_tiers, tier_headers,
                   use_ai, http, verbose, index, total):
    """Probe an endpoint across all active authorization tiers, returning Probes."""
    params_count = len(endpoint["params"])
    if verbose:
        print(f"\n[+] Testing endpoint ({index}/{total}): {endpoint['method']} {endpoint['path']}")
        names = [p["name"] for p in endpoint["params"]]
        print(f"    Parameters ({params_count}): {', '.join(names) if names else 'None'} | tiers: {','.join(active_tiers)}")

    if samples is None:
        samples = generate_param_samples(endpoint, use_ai=use_ai)

    test_cases = [({}, "empty")]
    if samples:
        test_cases.append((samples[0], "set_1"))
    if len(samples) > 1:
        test_cases.append((samples[1], "set_2"))

    probes = []
    for params, _case in test_cases:
        params_str = format_params_values(params)
        for tier in active_tiers:
            headers = dict(tier_headers.get(tier) or {})
            probes.append(_probe_once(endpoint, params, base_url, tier, params_str, headers, http, verbose))
    return probes

# -------------------------------------------------
# File Versioning
# -------------------------------------------------

def extract_hostname_from_url(base_url: str) -> str:
    """Extract hostname from base URL for file naming."""
    try:
        parsed = urlparse(base_url)
        hostname = parsed.hostname or parsed.netloc or "unknown"
        # Remove port if present
        hostname = hostname.split(":")[0]
        # Replace dots and special chars with hyphens
        hostname = re.sub(r'[^a-zA-Z0-9-]', '-', hostname)
        # Remove multiple consecutive hyphens
        hostname = re.sub(r'-+', '-', hostname)
        return hostname.lower()
    except Exception:
        return "unknown-host"

def get_versioned_filename(base_filename: str) -> str:
    """Get next versioned filename (e.g., hostname.csv -> hostname1.csv -> hostname2.csv)."""
    if not os.path.exists(base_filename):
        return base_filename
    
    # Extract base name and extension
    base_name, ext = os.path.splitext(base_filename)
    
    # Find all existing versions in the same directory
    directory = os.path.dirname(base_filename) or "."
    pattern = re.compile(rf"^{re.escape(base_name)}(\d+)?{re.escape(ext)}$")
    
    max_version = -1
    for filename in os.listdir(directory):
        match = pattern.match(filename)
        if match:
            version_str = match.group(1)
            if version_str:
                try:
                    version = int(version_str)
                    max_version = max(max_version, version)
                except ValueError:
                    pass
            else:
                # Base file exists (no number)
                max_version = max(max_version, -1)
    
    # Return next version
    next_version = max_version + 1
    if next_version == 0:
        # Base file exists, return version 1
        return f"{base_name}1{ext}"
    else:
        return f"{base_name}{next_version}{ext}"

# -------------------------------------------------
# Scan Runner (Resume-aware)
# -------------------------------------------------

def _expected_case_count(ep: Dict[str, Any], use_ai: bool) -> int:
    """How many test cases an endpoint yields: empty + (2 AI sets or 1 heuristic set)."""
    if not ep["params"]:
        return 1
    return 3 if use_ai else 2


def run_scan(url=None, file_path=None, output_file=None, verbose=False, use_ai=True, methods=None,
             max_rps=5.0, min_interval=0.05, rate_margin=2, max_retries=4, cooldown_cap=120.0,
             adaptive=True, respect_retry_after=True, tiers=None, trace=False,
             sim_strong=0.90, sim_shape=0.60):
    spec, base_url = load_openapi(url, file_path)
    endpoints = extract_endpoints(spec)

    if methods:
        allowed = {m.strip().upper() for m in methods if m.strip()}
        endpoints = [e for e in endpoints if e["method"] in allowed]

    total = len(endpoints)

    # Authorization tiers. A tier is probed only if its headers were supplied;
    # the unauthenticated tier is always present.
    tier_headers = {}
    if tiers:
        if tiers.get("user"):
            tier_headers[USER] = dict(tiers["user"])
        if tiers.get("admin"):
            tier_headers[ADMIN] = dict(tiers["admin"])
    active_tiers = [UNAUTH] + [t for t in (USER, ADMIN) if t in tier_headers]
    has_user = USER in tier_headers
    has_admin = ADMIN in tier_headers

    # Output paths: findings (signal only) always; full trace only on request.
    if output_file is None:
        output_file = f"{extract_hostname_from_url(base_url)}.csv"
    base_name, _ext = os.path.splitext(output_file)
    findings_file = base_name + ".findings.csv"
    trace_file = base_name + ".trace.csv"

    http = SafeHTTP(
        max_rps=max_rps, min_interval=min_interval, rate_margin=rate_margin,
        max_retries=max_retries, cooldown_cap=cooldown_cap, adaptive=adaptive,
        respect_retry_after=respect_retry_after,
    )
    opts = {"sim_strong": sim_strong, "sim_shape": sim_shape,
            "has_user": has_user, "has_admin": has_admin}

    if verbose:
        print("[*] OpenAPI loaded successfully")
        print(f"[*] Base URL: {base_url}")
        print(f"[*] Total endpoints detected: {total}")
        print(f"[*] Mode: {'AI' if use_ai else 'no-AI (--skip-ai-params)'} | tiers: {','.join(active_tiers)}")

    all_probes = []
    all_verdicts = []
    for ep_idx, ep in enumerate(endpoints, 1):
        samples = generate_param_samples(ep, use_ai=use_ai)
        probes = probe_endpoint(
            ep, base_url, samples, active_tiers, tier_headers,
            use_ai, http, verbose, ep_idx, total
        )
        all_probes.extend(probes)

        # Decide per param-set, across whatever tiers were probed.
        groups = {}
        for p in probes:
            groups.setdefault(p.params_values, []).append(p)
        for _pv, grp in groups.items():
            all_verdicts.append(decision.decide(grp, opts))
            bfla = decision.bfla_verdict(grp, opts)
            if bfla:
                all_verdicts.append(bfla)

        update_progress(ep_idx, total)

    http.close()

    reporting.write_findings(findings_file, all_verdicts)
    if trace:
        reporting.write_trace(trace_file, all_probes)

    reporting.console_summary(all_verdicts, http, findings_file)
    if trace:
        extra = " (+ .xlsx)" if reporting.OPENPYXL else ""
        print(f"Full trace -> {trace_file}{extra}")

    return all_verdicts
