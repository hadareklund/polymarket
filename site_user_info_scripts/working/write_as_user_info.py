#!/usr/bin/env python3
"""Fetch Write.as user/collection info via the public REST API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Write.as user info by username.")
    parser.add_argument("username", help="Write.as username (collection alias)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    url = f"https://write.as/api/collections/{args.username}"
    try:
        resp = fetch_json(url, timeout=args.timeout)
        data = resp.get("data") or {}
        if resp.get("code", 200) not in (200, None):
            raise RuntimeError(f"API error: {resp}")
        result = {
            "site": "Write.as",
            "username": data.get("alias") or args.username,
            "title": data.get("title"),
            "description": data.get("description"),
            "total_posts": data.get("total_posts"),
            "total_views": data.get("views"),
            "is_public": data.get("public"),
            "format": data.get("format"),
            "profile_url": data.get("url") or f"https://write.as/{args.username}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
