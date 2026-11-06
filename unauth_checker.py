#!/usr/bin/env python3

import argparse
from engine import run_scan

def main():
    parser = argparse.ArgumentParser(description="Unauthenticated API Checker")
    parser.add_argument("-u", "--url", help="URL to OpenAPI JSON", default=None)
    parser.add_argument("-f", "--file", help="Path to local OpenAPI JSON", default=None)
    parser.add_argument(
        "-o", "--output",
        help="CSV output file (auto-generated from hostname if not provided, with versioning)",
        default=None
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show execution progress and runtime activity"
    )
    parser.add_argument(
        "--skip-ai-params",
        action="store_true",
        help="Skip AI-generated parameter values (ai_agent.py). Runs only the "
             "core checker using spec-derived / type-based values, with no API "
             "key required."
    )
    parser.add_argument(
        "--methods",
        help="Comma-separated HTTP methods to test (e.g. 'get,post'). Default: all.",
        default=None
    )
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

    methods = [m for m in args.methods.split(",")] if args.methods else None

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
    )

if __name__ == "__main__":
    main()
