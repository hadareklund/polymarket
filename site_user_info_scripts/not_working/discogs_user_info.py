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
        data = fetch_json(f"https://api.discogs.com/users/{args.username}", timeout=args.timeout)
        if "message" in data: raise RuntimeError(data["message"])
        result = {
            "site": "Discogs",
            "username": data.get("username"),
            "real_name": data.get("name"),
            "location": data.get("location"),
            "profile": data.get("profile"),
            "followers": data.get("num_collection"),
            "wantlist": data.get("num_wantlist"),
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
