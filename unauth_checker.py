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
        methods=methods
    )

if __name__ == "__main__":
    main()
