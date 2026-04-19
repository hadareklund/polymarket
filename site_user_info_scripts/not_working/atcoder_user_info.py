#!/usr/bin/env python3
"""Fetch user profile information from AtCoder."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get AtCoder user info by username.")
    parser.add_argument("username", help="AtCoder username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://atcoder.jp/users/{args.username}/history/json", timeout=args.timeout)
        contests = data if isinstance(data, list) else []
        result = {
            "site": "AtCoder",
            "username": args.username,
            "contests_participated": len(contests),
            "last_contest": contests[-1].get("ContestName") if contests else None,
            "last_rating": contests[-1].get("NewRating") if contests else None,
            "profile_url": f"https://atcoder.jp/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
