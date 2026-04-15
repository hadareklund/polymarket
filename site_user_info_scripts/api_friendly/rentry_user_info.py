#!/usr/bin/env python3
"""Fetch Rentry raw paste content by paste ID."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Get Rentry data by paste ID. Rentry does not expose user-account lookup by username."
        )
    )
    parser.add_argument("username", help="Paste ID (not a username)")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument(
        "--max-preview-chars",
        type=int,
        default=1000,
        help="Maximum characters to include in preview",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    paste_id = args.username
    endpoint = f"https://rentry.co/{quote(paste_id)}/raw"

    try:
        raw_text = fetch_text(endpoint, timeout=args.timeout)
        max_preview = max(0, args.max_preview_chars)
        preview = raw_text[:max_preview]

        result = {
            "site": "Rentry",
            "endpoint": endpoint,
            "lookup": paste_id,
            "lookup_type": "paste_id",
            "character_count": len(raw_text),
            "preview": preview,
            "note": "Rentry has no public username account endpoint; this script resolves paste content by paste ID.",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
