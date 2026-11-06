#!/usr/bin/env python3

import argparse
from engine import run_scan, parse_header

def main():
    parser = argparse.ArgumentParser(
        description="Unauthenticated API Checker — authorization-tier differential scanner"
    )
    parser.add_argument("-u", "--url", help="URL to OpenAPI JSON", default=None)
    parser.add_argument("-f", "--file", help="Path to local OpenAPI JSON", default=None)
    parser.add_argument(
        "-o", "--output",
        help="Base output name (findings + optional trace derive from this; "
             "auto-generated from hostname if not provided)",
        default=None
    )
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show execution progress and runtime activity")
    parser.add_argument(
        "--skip-ai-params", action="store_true",
        help="Skip AI-generated parameter values (ai_agent.py). Uses spec-derived "
             "/ type-based values only, with no API key required."
    )
    parser.add_argument(
        "-x", "--user-header", action="append", default=None, metavar="HEADER",
        help="Authenticated (user-tier) header, e.g. -x 'Authorization: Bearer …' "
             "or -x 'X-API-Key: k'. Repeatable. Full 'Name: value' or bare token."
    )
    parser.add_argument(
        "-a", "--admin-header", action="append", default=None, metavar="HEADER",
        help="Privileged (admin-tier) header, compared against the user tier to "
             "detect privilege escalation / BFLA. Repeatable."
    )
    parser.add_argument("--methods",
                        help="Comma-separated HTTP methods to test (e.g. 'get,post'). "
                             "When -a is set and this is omitted, defaults to get,head.",
                        default=None)
    parser.add_argument("--trace", action="store_true",
                        help="Also write the full per-call log (every request/tier) "
                             "as CSV (and .xlsx if openpyxl is installed).")
    parser.add_argument("--similarity", type=float, default=0.90,
                        help="Body-similarity threshold for 'same data' (default 0.90)")

    # Rate-limit management
    parser.add_argument("--max-rps", type=float, default=5.0,
                        help="Hard ceiling on requests/sec per host (default 5)")
    parser.add_argument("--min-interval", type=float, default=0.05,
                        help="Minimum seconds between requests per host (default 0.05)")
    parser.add_argument("--max-retries", type=int, default=4,
                        help="Per-request retry budget when rate-limited (default 4)")
    parser.add_argument("--cooldown-cap", type=float, default=120.0,
                        help="Max seconds to sleep for a single rate-limit cooldown (default 120)")

    args = parser.parse_args()

    if not args.url and not args.file:
        print("[-] Either --url or --file must be provided")
        return

    methods = [m.strip() for m in args.methods.split(",")] if args.methods else None
    if args.admin_header and not args.methods:
        methods = ["GET", "HEAD"]
        print("[!] -a set without --methods: restricting to GET,HEAD to avoid mutating "
              "data. Pass --methods to override.")

    tiers = {}
    if args.user_header:
        tiers["user"] = [parse_header(h) for h in args.user_header]
    if args.admin_header:
        tiers["admin"] = [parse_header(h) for h in args.admin_header]

    run_scan(
        url=args.url,
        file_path=args.file,
        output_file=args.output,
        verbose=args.verbose,
        use_ai=not args.skip_ai_params,
        methods=methods,
        max_rps=args.max_rps,
        min_interval=args.min_interval,
        max_retries=args.max_retries,
        cooldown_cap=args.cooldown_cap,
        tiers=tiers or None,
        trace=args.trace,
        sim_strong=args.similarity,
    )

if __name__ == "__main__":
    main()
