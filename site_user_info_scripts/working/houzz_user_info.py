#!/usr/bin/env python3
"""Fetch user profile information from Houzz (HTML + embedded JSON)."""

from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Houzz user info by username.")
    parser.add_argument("username", help="Houzz username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.houzz.com/user/{args.username}"
        html = fetch_text(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_m and "Page Not Found" in title_m.group(1):
            raise RuntimeError(f"User '{args.username}' not found on Houzz.")

        # Extract embedded UserProfileStore JSON from script tags
        user_data: dict = {}
        for script_m in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.S):
            content = script_m.group(1)
            if "UserProfileStore" not in content:
                continue
            user_m = re.search(
                r'"user":\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',
                content,
            )
            if user_m:
                try:
                    user_data = _json.loads(user_m.group(1))
                    break
                except _json.JSONDecodeError:
                    pass

        stats = user_data.get("stats", {})
        result = {
            "site": "Houzz",
            "username": user_data.get("userName") or args.username,
            "display_name": user_data.get("displayName"),
            "is_professional": user_data.get("isProfessional"),
            "follower_count": stats.get("followerCount"),
            "following_count": stats.get("followingCount"),
            "galleries_count": stats.get("galleriesCount"),
            "projects_count": stats.get("projectsCount"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
