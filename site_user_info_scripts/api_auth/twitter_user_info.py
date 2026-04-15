#!/usr/bin/env python3
"""Fetch Twitter/X user profile information by username."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, require_secret


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Get Twitter/X user info by username (requires bearer token)."
    )
    parser.add_argument("username", help="Twitter/X username without @")
    parser.add_argument(
        "--bearer-token",
        help="Twitter API Bearer token (or set TWITTER_BEARER_TOKEN).",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        bearer_token = require_secret(args.bearer_token, "TWITTER_BEARER_TOKEN")
        endpoint = f"https://api.twitter.com/2/users/by/username/{quote(args.username)}"
        params = {
            "user.fields": "created_at,description,location,name,profile_image_url,public_metrics,url,verified",
        }
        data = fetch_json(
            endpoint,
            headers={"Authorization": f"Bearer {bearer_token}"},
            params=params,
            timeout=args.timeout,
        )

        profile = data.get("data") or {}
        metrics = profile.get("public_metrics") or {}

        result = {
            "site": "Twitter",
            "username": profile.get("username") or args.username,
            "id": profile.get("id"),
            "name": profile.get("name"),
            "description": profile.get("description"),
            "location": profile.get("location"),
            "created_at": profile.get("created_at"),
            "verified": profile.get("verified"),
            "followers_count": metrics.get("followers_count"),
            "following_count": metrics.get("following_count"),
            "tweet_count": metrics.get("tweet_count"),
            "listed_count": metrics.get("listed_count"),
            "profile_url": profile.get("url")
            or f"https://x.com/{quote(args.username)}",
            "api_errors": data.get("errors"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
