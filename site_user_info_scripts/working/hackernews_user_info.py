#!/usr/bin/env python3
"""Fetch user profile information from Hacker News public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, unix_to_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Hacker News user info by username.")
    parser.add_argument("username", help="Hacker News username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = (
        f"https://hacker-news.firebaseio.com/v0/user/{quote(args.username)}.json"
    )
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        if data is None:
            raise RuntimeError("User not found.")
        submitted = data.get("submitted") or []
        result = {
            "site": "HackerNews",
            "username": data.get("id"),
            "created_unix": data.get("created"),
            "created_at": unix_to_iso(data.get("created")),
            "karma": data.get("karma"),
            "bio": data.get("about"),
            "submission_count": len(submitted),
            "profile_url": f"https://news.ycombinator.com/user?id={quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
