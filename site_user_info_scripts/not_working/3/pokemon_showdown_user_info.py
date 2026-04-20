#!/usr/bin/env python3
"""Fetch user profile information from Pokemon Showdown."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Pokemon Showdown user info by username.")
    parser.add_argument("username", help="Pokemon Showdown username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://pokemonshowdown.com/users/{args.username}.json", timeout=args.timeout)
        if not data.get("userid"): raise RuntimeError("User not found.")
        result = {
            "site": "Pokemon Showdown",
            "username": data.get("name"),
            "userid": data.get("userid"),
            "avatar": data.get("avatar"),
            "profile_url": f"https://pokemonshowdown.com/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
