import json
import csv
import sys
import os
import re
import requests
from urllib.parse import urlparse
from typing import Dict, Any, List, Tuple, Optional
from ai_agent import AIAgent

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
# CSV Helpers (Resume-safe)
# -------------------------------------------------

def write_csv_header_if_needed(filename: str):
    if not os.path.exists(filename):
        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
                writer.writeheader()
        except Exception as e:
            raise ValueError(f"Failed to create CSV file {filename}: {e}")

def append_csv_row(filename: str, row: Dict[str, Any]):
    try:
        with open(filename, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writerow(row)
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

def extract_endpoints(spec: Dict) -> List[Dict[str, Any]]:
    endpoints = []

    for path, methods in spec.get("paths", {}).items():
        if not isinstance(methods, dict):
            continue

        for method, details in methods.items():
            if not isinstance(details, dict):
                continue

            params = []
            for p in details.get("parameters", []):
                params.append({
                    "name": p.get("name"),
                    "type": p.get("schema", {}).get("type", "string"),
                    "description": p.get("description", "")
                })

            endpoints.append({
                "path": path,
                "method": method.upper(),
                "params": params
            })

    return endpoints

# -------------------------------------------------
# AI Sample Generation (Max 2 sets)
# -------------------------------------------------

def generate_param_samples(endpoint: Dict[str, Any]) -> List[Dict[str, str]]:
    if not endpoint["params"]:
        return [{}]

    agent = get_agent()
    samples = []
    for _ in range(2):
        sample = {}
        for p in endpoint["params"]:
            sample[p["name"]] = agent.generate_sample_value(
                p["type"], p["name"], p["description"]
            )
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

def test_endpoint(endpoint, base_url, csv_file, index, total, verbose):
    # Ensure base_url ends without slash and path starts with slash
    base = base_url.rstrip("/")
    path = endpoint['path'] if endpoint['path'].startswith("/") else f"/{endpoint['path']}"
    url = f"{base}{path}"
    
    params_count = len(endpoint["params"])
    
    if verbose:
        print(f"\n[+] Testing endpoint ({index}/{total}): {endpoint['method']} {endpoint['path']}")
        params_list = [p["name"] for p in endpoint["params"]]
        print(f"    Detected parameters ({params_count}): {', '.join(params_list) if params_list else 'None'}")

    # Generate 2 sets of parameter samples
    samples = generate_param_samples(endpoint)
    
    # Test 3 times: empty params, set 1, set 2
    test_cases = [({}, "empty")]
    
    if samples and len(samples) > 0:
        test_cases.append((samples[0], "set_1"))
    if samples and len(samples) > 1:
        test_cases.append((samples[1], "set_2"))
    
    if verbose:
        print(f"    [*] Agent generating sample values...")
        if params_count > 0:
            print(f"    [*] {len(samples) * params_count} sample values created")
        print(f"    [*] Testing {len(test_cases)} cases: empty params + {len(samples)} sample sets")

    for case_idx, (params, case_name) in enumerate(test_cases, 1):
        statuses = set()
        params_str = format_params_values(params)
        response_body = ""
        
        if verbose:
            if case_name == "empty":
                print(f"    [*] Test case {case_idx}/3: Empty parameters")
            else:
                print(f"    [*] Test case {case_idx}/3: {case_name} - {params_str}")

        try:
            r = requests.request(
                endpoint["method"],
                url,
                params=params,
                timeout=10
            )

            statuses.add(r.status_code)
            # Capture response body (cleaned/truncated for CSV)
            response_body = clean_response_body(r.text, limit=2000)  # Increased limit for CSV

            if verbose:
                print(f"        → Status: {r.status_code}")
                print("        → Response:")
                print(clean_response_body(r.text))

        except requests.RequestException as e:
            if verbose:
                print(f"        [!] Error: {e}")
            statuses.add("ERROR")
            response_body = f"Request Error: {str(e)}"

        confidence = 60 if 200 in statuses else 0
        confidence_level = "Medium" if 200 in statuses else "Inconclusive"

        result = {
            "endpoint": endpoint["path"],
            "method": endpoint["method"],
            "params_count": params_count,
            "params_values": params_str,
            "status_codes": ",".join(map(str, sorted(statuses))) if statuses else "N/A",
            "response": response_body,
            "confidence": confidence,
            "confidence_level": confidence_level,
            "notes": f"Test case: {case_name}"
        }

        append_csv_row(csv_file, result)

    if verbose:
        print("    [+] Endpoint evaluation completed")
        print(f"    [+] {len(test_cases)} result(s) appended to CSV")

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

def run_scan(url=None, file_path=None, output_file=None, verbose=False):
    spec, base_url = load_openapi(url, file_path)
    endpoints = extract_endpoints(spec)
    total = len(endpoints)

    # Generate output filename from hostname if not provided
    if output_file is None:
        hostname = extract_hostname_from_url(base_url)
        output_file = f"{hostname}.csv"
    
    # Get versioned filename
    output_file = get_versioned_filename(output_file)
    
    write_csv_header_if_needed(output_file)
    completed = load_completed_endpoints(output_file)

    if verbose:
        print("[*] OpenAPI loaded successfully")
        print(f"[*] Base URL: {base_url}")
        print(f"[*] Total endpoints detected: {total}")
        print(f"[*] Output file: {output_file}")
        print(f"[*] Resuming scan, {len(completed)} test cases already completed\n")

    completed_count = len(completed)
    total_test_cases = total * 3  # Each endpoint has 3 test cases

    for ep_idx, ep in enumerate(endpoints, 1):
        # Test endpoint with 3 cases (empty, set1, set2)
        # Check if all 3 cases are completed
        empty_key = f"{ep['method']} {ep['path']} {{}}"
        set1_key = None
        set2_key = None
        
        if ep["params"]:
            samples = generate_param_samples(ep)
            if samples:
                set1_key = f"{ep['method']} {ep['path']} {format_params_values(samples[0])}"
            if len(samples) > 1:
                set2_key = f"{ep['method']} {ep['path']} {format_params_values(samples[1])}"
        
        # Check if all test cases are completed
        all_completed = empty_key in completed
        if set1_key:
            all_completed = all_completed and (set1_key in completed)
        if set2_key:
            all_completed = all_completed and (set2_key in completed)
        
        if all_completed:
            # Count completed test cases for progress
            test_case_count = 1 + (1 if set1_key else 0) + (1 if set2_key else 0)
            completed_count += test_case_count
            update_progress(completed_count, total_test_cases)
            continue

        test_endpoint(
            ep,
            base_url,
            output_file,
            ep_idx,
            total,
            verbose
        )
        # Each endpoint adds 3 test cases
        completed_count += 3
        update_progress(completed_count, total_test_cases)

    if verbose:
        print("\n[*] Scan completed successfully")
        print(f"[*] Results stored in {output_file}")
