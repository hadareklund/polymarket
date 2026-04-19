#!/usr/bin/env python3
"""Fetch user profile information from Mixcloud public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Mixcloud user info by username.")
    parser.add_argument("username", help="Mixcloud username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _fetch_cloudcasts(username: str, timeout: int) -> list[dict]:
    try:
        data = fetch_json(
            f"https://api.mixcloud.com/{quote(username)}/cloudcasts/?limit=10",
            timeout=timeout,
        )
        return [
            {
                "name": c.get("name"),
                "url": c.get("url"),
                "play_count": c.get("play_count"),
                "listener_count": c.get("listener_count"),
                "favorite_count": c.get("favorite_count"),
                "created_time": c.get("created_time"),
                "tags": [t.get("name") for t in (c.get("tags") or [])],
            }
            for c in (data.get("data") or [])
        ]
    except Exception:
        return []


def main() -> int:
    args = parse_args()
    endpoint = f"https://api.mixcloud.com/{quote(args.username)}/"
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        username = data.get("username") or args.username
        cloudcasts = _fetch_cloudcasts(username, args.timeout)

        result = {
            "site": "Mixcloud",
            "username": username,
            "display_name": data.get("name"),
            "bio": data.get("biog"),
            "city": data.get("city"),
            "country": data.get("country"),
            "follower_count": data.get("follower_count"),
            "following_count": data.get("following_count"),
            "is_pro": data.get("is_pro"),
            "cloudcasts": cloudcasts,
            "pictures": data.get("pictures"),
            "profile_url": data.get("url") or f"https://www.mixcloud.com/{quote(args.username)}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
