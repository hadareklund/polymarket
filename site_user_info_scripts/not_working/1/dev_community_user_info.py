#!/usr/bin/env python3
"""Fetch user profile information from DEV Community."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get DEV Community user info by username.")
    parser.add_argument("username", help="DEV Community username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://dev.to/api/users/by_username?url={args.username}",
            timeout=args.timeout,
        )
        if "error" in data:
            raise RuntimeError(data.get("error", "Not found."))
        result = {
            "site": "DEV Community",
            "username": data.get("username"),
            "name": data.get("name"),
            "bio": data.get("summary") or None,
            "location": data.get("location") or None,
            "website": data.get("website_url") or None,
            "twitter": data.get("twitter_username") or None,
            "github": data.get("github_username") or None,
            "followers": data.get("followers_count"),
            "joined": data.get("joined_at"),
            "avatar_url": data.get("profile_image"),
            "profile_url": f"https://dev.to/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
