#!/usr/bin/env python3
"""Fetch Reddit user profile information using OAuth access token."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, load_env_file, print_json, require_secret, unix_to_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Get Reddit user info by username (requires OAuth access token)."
    )
    parser.add_argument("username", help="Reddit username without u/")
    parser.add_argument(
        "--access-token",
        help="OAuth access token (or set REDDIT_ACCESS_TOKEN in env or .env).",
    )
    parser.add_argument(
        "--user-agent",
        default="site-user-info-scripts/1.0",
        help="Custom User-Agent header required by Reddit API.",
    )
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    load_env_file(start_dir=Path(__file__).resolve().parent)
    args = parse_args()
    try:
        access_token = require_secret(args.access_token, "REDDIT_ACCESS_TOKEN")
        endpoint = f"https://oauth.reddit.com/user/{quote(args.username)}/about"
        data = fetch_json(
            endpoint,
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": args.user_agent,
            },
            timeout=args.timeout,
        )
        profile = data.get("data") or {}
        subreddit = profile.get("subreddit") or {}

        result = {
            "site": "Reddit",
            "username": profile.get("name") or args.username,
            "id": profile.get("id"),
            "created_utc": profile.get("created_utc"),
            "created_at": unix_to_iso(profile.get("created_utc")),
            "comment_karma": profile.get("comment_karma"),
            "link_karma": profile.get("link_karma"),
            "total_karma": (
                (profile.get("comment_karma") or 0) + (profile.get("link_karma") or 0)
            ),
            "is_gold": profile.get("is_gold"),
            "is_mod": profile.get("is_mod"),
            "bio": subreddit.get("public_description") or subreddit.get("description"),
            "profile_url": f"https://www.reddit.com/user/{quote(args.username)}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
