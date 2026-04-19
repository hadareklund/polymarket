#!/usr/bin/env python3
"""Fetch user profile information from Wikipedia."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Wikipedia user info by username.")
    parser.add_argument("username", help="Wikipedia username")
    parser.add_argument("--lang", default="en", help="Wiki language code")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://{args.lang}.wikipedia.org/api/rest_v1/page/summary/User:{quote(args.username)}"
        data = fetch_json(url, timeout=args.timeout)
        result = {
            "site": "Wikipedia",
            "username": args.username,
            "page_title": data.get("title"),
            "extract": data.get("extract"),
            "edit_count": None,
            "profile_url": f"https://{args.lang}.wikipedia.org/wiki/User:{quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
