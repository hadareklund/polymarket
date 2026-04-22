#!/usr/bin/env python3
"""Fetch Know Your Meme user profile info via HTML scraping."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Know Your Meme user info by username.")
    parser.add_argument("username", help="Know Your Meme username (URL slug)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    url = f"https://knowyourmeme.com/users/{args.username}"
    try:
        html = fetch_text(url, headers={"User-Agent": UA}, timeout=args.timeout)

        title_m = re.search(r"<title>([^<]+)'s Profile", html)
        if not title_m:
            raise RuntimeError(f"User '{args.username}' not found or unexpected page.")
        display_name = title_m.group(1).strip()

        avatar_m = re.search(r'class="big"[^>]+data-src="([^"]+)"', html)
        role_m = re.search(r'profile-avatar-role[^>]*><span[^>]*>([^<]+)<', html)
        joined_m = re.search(r"class='timeago'\s+title='([^']+)'", html)
        followers_m = re.search(r"Followers\s*<span[^>]*>\((\d+)\)<", html)
        following_m = re.search(r"Following\s*<span[^>]*>\((\d+)\)<", html)
        location_m = re.search(r"Location:\s*([^<]+)<", html)

        result = {
            "site": "Know Your Meme",
            "username": args.username,
            "display_name": display_name,
            "role": role_m.group(1).strip() if role_m else None,
            "location": location_m.group(1).strip() if location_m else None,
            "joined": joined_m.group(1) if joined_m else None,
            "followers": int(followers_m.group(1)) if followers_m else None,
            "following": int(following_m.group(1)) if following_m else None,
            "avatar_url": avatar_m.group(1) if avatar_m else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
