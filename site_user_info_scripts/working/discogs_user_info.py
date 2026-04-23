#!/usr/bin/env python3
"""Fetch user profile information from Discogs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Discogs user info by username.")
    parser.add_argument("username", help="Discogs username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://api.discogs.com/users/{args.username}",
            headers={"User-Agent": "PolymarketOSINT/1.0"},
            timeout=args.timeout,
        )
        if "message" in data:
            raise RuntimeError(data["message"])
        result = {
            "site": "Discogs",
            "username": data.get("username"),
            "name": data.get("name") or None,
            "location": data.get("location") or None,
            "bio": data.get("profile") or None,
            "home_page": data.get("home_page") or None,
            "avatar_url": data.get("avatar_url"),
            "rank": data.get("rank"),
            "num_collection": data.get("num_collection"),
            "num_wantlist": data.get("num_wantlist"),
            "num_for_sale": data.get("num_for_sale"),
            "releases_contributed": data.get("releases_contributed"),
            "registered": data.get("registered"),
            "profile_url": data.get("uri"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
