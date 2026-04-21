#!/usr/bin/env python3
"""Fetch user profile information from Mastodon Cloud."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Mastodon Cloud user info by username.")
    parser.add_argument("username", help="Mastodon Cloud username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://mastodon.cloud/api/v1/accounts/lookup?acct={args.username}", timeout=args.timeout)
        if "error" in data: raise RuntimeError(data.get("error", "Not found."))
        result = {
            "site": "Mastodon Cloud",
            "username": data.get("acct"),
            "display_name": data.get("display_name"),
            "bio": data.get("note"),
            "followers": data.get("followers_count"),
            "following": data.get("following_count"),
            "posts": data.get("statuses_count"),
            "avatar_url": data.get("avatar"),
            "created_at": data.get("created_at"),
            "profile_url": data.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
