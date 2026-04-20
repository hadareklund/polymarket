#!/usr/bin/env python3
"""Fetch user profile information from SublimeForum (Discourse JSON API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get SublimeForum user info by username.")
    parser.add_argument("username", help="SublimeForum username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://forum.sublimetext.com/u/{args.username}.json"
        data = fetch_json(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        user = data.get("user", {})
        avatar = user.get("avatar_template", "")
        if avatar and "{size}" in avatar:
            avatar = avatar.replace("{size}", "120")
        if avatar and avatar.startswith("/"):
            avatar = "https://forum.sublimetext.com" + avatar
        result = {
            "site": "SublimeForum",
            "username": args.username,
            "display_name": user.get("name") or None,
            "title": user.get("title") or None,
            "bio": user.get("bio_cooked") or user.get("bio_raw") or None,
            "avatar_url": avatar or None,
            "website": user.get("website") or None,
            "location": user.get("location") or None,
            "trust_level": user.get("trust_level"),
            "post_count": user.get("post_count"),
            "topic_count": user.get("topic_count"),
            "likes_given": user.get("likes_given"),
            "likes_received": user.get("likes_received"),
            "days_visited": user.get("days_visited"),
            "created_at": user.get("created_at"),
            "last_seen_at": user.get("last_seen_at"),
            "profile_url": f"https://forum.sublimetext.com/u/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
