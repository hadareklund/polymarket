#!/usr/bin/env python3
"""Fetch user profile information from Codewars."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Codewars user info by username.")
    parser.add_argument("username", help="Codewars username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://www.codewars.com/api/v1/users/{args.username}", timeout=args.timeout)
        if data.get("reason") == "not found": raise RuntimeError("User not found.")
        result = {
            "site": "Codewars",
            "username": data.get("username"),
            "name": data.get("name"),
            "honor": data.get("honor"),
            "clan": data.get("clan"),
            "city": data.get("city"),
            "rank": (data.get("ranks") or {}).get("overall", {}).get("name"),
            "leaderboard_position": data.get("leaderboardPosition"),
            "languages": list((data.get("ranks") or {}).get("languages", {}).keys()),
            "profile_url": f"https://www.codewars.com/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
