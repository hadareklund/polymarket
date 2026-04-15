#!/usr/bin/env python3
"""Fetch StackOverflow user matches by inname query."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, load_env_file, print_json, unix_to_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Search StackOverflow users by name/username."
    )
    parser.add_argument("username", help="StackOverflow username or partial name")
    parser.add_argument(
        "--api-key",
        help="StackExchange API key (optional, or set STACKEXCHANGE_API_KEY in env or .env).",
    )
    parser.add_argument(
        "--pagesize",
        type=int,
        default=10,
        help="Number of results to return (default: 10)",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _compact_item(item: dict) -> dict:
    return {
        "user_id": item.get("user_id"),
        "display_name": item.get("display_name"),
        "reputation": item.get("reputation"),
        "badges": item.get("badge_counts"),
        "website_url": item.get("website_url"),
        "location": item.get("location"),
        "creation_date": unix_to_iso(item.get("creation_date")),
        "last_access_date": unix_to_iso(item.get("last_access_date")),
        "profile_url": item.get("link"),
    }


def main() -> int:
    load_env_file(start_dir=Path(__file__).resolve().parent)
    args = parse_args()
    api_key = args.api_key or os.getenv("STACKEXCHANGE_API_KEY")
    endpoint = "https://api.stackexchange.com/2.3/users"
    params = {
        "inname": args.username,
        "site": "stackoverflow",
        "order": "desc",
        "sort": "reputation",
        "pagesize": max(1, min(args.pagesize, 100)),
        "key": api_key,
    }
    try:
        data = fetch_json(endpoint, params=params, timeout=args.timeout)
        items = data.get("items") or []
        result = {
            "site": "StackOverflow",
            "query": args.username,
            "match_count": len(items),
            "has_more": data.get("has_more"),
            "quota_remaining": data.get("quota_remaining"),
            "results": [_compact_item(item) for item in items],
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
