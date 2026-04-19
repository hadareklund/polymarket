#!/usr/bin/env python3
"""Fetch user profile information from DailyMotion."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get DailyMotion user info by username.")
    parser.add_argument("username", help="DailyMotion username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.dailymotion.com/user/{args.username}?fields=id,url,username,screenname,description,avatar_720_url,followers_total,following_total,videos_total,created_time", timeout=args.timeout)
        if "error" in data: raise RuntimeError(str(data["error"]))
        result = {
            "site": "DailyMotion",
            "username": data.get("username"),
            "display_name": data.get("screenname"),
            "bio": data.get("description"),
            "avatar_url": data.get("avatar_720_url"),
            "followers": data.get("followers_total"),
            "following": data.get("following_total"),
            "videos": data.get("videos_total"),
            "created_at": data.get("created_time"),
            "profile_url": data.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
