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

    args = parser.parse_args()

    if not args.url and not args.file:
        print("[-] Either --url or --file must be provided")
        return

    run_scan(
        url=args.url,
        file_path=args.file,
        output_file=args.output,
        verbose=args.verbose
    )

if __name__ == "__main__":
    main()
