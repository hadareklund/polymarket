#!/usr/bin/env python3
"""Fetch user profile information from Codeforces."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Codeforces user info by username.")
    parser.add_argument("username", help="Codeforces username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://codeforces.com/api/user.info?handles={args.username}", timeout=args.timeout)
        if data.get("status") != "OK": raise RuntimeError(data.get("comment", "Not found."))
        u = (data.get("result") or [{}])[0]
        result = {
            "site": "Codeforces",
            "username": u.get("handle"),
            "rank": u.get("rank"),
            "max_rank": u.get("maxRank"),
            "rating": u.get("rating"),
            "max_rating": u.get("maxRating"),
            "country": u.get("country"),
            "city": u.get("city"),
            "organization": u.get("organization"),
            "contribution": u.get("contribution"),
            "profile_url": f"https://codeforces.com/profile/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
