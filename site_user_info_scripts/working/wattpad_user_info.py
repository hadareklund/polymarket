#!/usr/bin/env python3
"""Fetch user profile information from Wattpad's public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json

FIELDS = "username,name,description,avatar,numStoriesPublished,numFollowers,numFollowing,createDate"


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Wattpad user info by username.")
    parser.add_argument("username", help="Wattpad username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://www.wattpad.com/api/v3/users/{args.username}",
            params={"fields": FIELDS},
            timeout=args.timeout,
        )
        if "error" in data:
            raise RuntimeError(data.get("error", "Not found"))
        result = {
            "site": "Wattpad",
            "username": data.get("username"),
            "name": data.get("name"),
            "bio": data.get("description"),
            "avatar_url": data.get("avatar"),
            "stories": data.get("numStoriesPublished"),
            "followers": data.get("numFollowers"),
            "following": data.get("numFollowing"),
            "joined": data.get("createDate"),
            "profile_url": f"https://www.wattpad.com/user/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
