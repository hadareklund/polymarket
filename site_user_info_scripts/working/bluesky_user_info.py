#!/usr/bin/env python3
"""Fetch user profile information from Bluesky (AT Protocol public API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Bluesky user info by handle.")
    parser.add_argument("username", help="Bluesky handle (e.g. user.bsky.social)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={args.username}",
            timeout=args.timeout,
        )
        if "error" in data:
            raise RuntimeError(data.get("message", "Not found."))
        result = {
            "site": "Bluesky",
            "username": data.get("handle"),
            "display_name": data.get("displayName"),
            "bio": data.get("description"),
            "followers": data.get("followersCount"),
            "following": data.get("followsCount"),
            "posts": data.get("postsCount"),
            "avatar_url": data.get("avatar"),
            "profile_url": f"https://bsky.app/profile/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
