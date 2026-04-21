#!/usr/bin/env python3
"""Fetch user profile information from Car Talk Community (Discourse JSON API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json

_BASE = "https://community.cartalk.com"


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Car Talk Community user info by username.")
    parser.add_argument("username", help="Car Talk Community username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"{_BASE}/u/{args.username}.json",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=args.timeout,
        )
        if "errors" in data:
            raise RuntimeError(str(data["errors"]))

        user = data.get("user", data)
        avatar_tmpl = user.get("avatar_template", "")
        avatar_url = (
            (_BASE + avatar_tmpl.replace("{size}", "240"))
            if avatar_tmpl.startswith("/")
            else avatar_tmpl.replace("{size}", "240")
        ) or None

        result = {
            "site": "Car Talk Community",
            "username": user.get("username"),
            "display_name": user.get("name"),
            "title": user.get("title"),
            "bio": user.get("bio_excerpt"),
            "trust_level": user.get("trust_level"),
            "moderator": user.get("moderator"),
            "badge_count": user.get("badge_count"),
            "profile_views": user.get("profile_view_count"),
            "last_seen_at": user.get("last_seen_at"),
            "created_at": user.get("created_at"),
            "avatar_url": avatar_url,
            "profile_url": f"{_BASE}/u/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
