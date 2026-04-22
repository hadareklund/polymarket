#!/usr/bin/env python3
"""Fetch user profile information from Wikidot (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Wikidot user info by username.")
    parser.add_argument("username", help="Wikidot username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.wikidot.com/user:info/{args.username}"
        html = fetch_text(url, headers={"User-Agent": UA}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>Wikidot\.com:\s*([^<]+)</title>", html, re.I)
        display_name = title_m.group(1).strip() if title_m else args.username

        uid_m = re.search(r"USERINFO\.userId\s*=\s*(\d+)", html)
        user_id = uid_m.group(1) if uid_m else None

        avatar_url = (
            f"https://www.wikidot.com/avatar.php?userid={user_id}" if user_id else None
        )

        karma_m = re.search(r"Karma level.*?<dd[^>]*>\s*(\S+)", html, re.I | re.S)
        karma = karma_m.group(1).strip() if karma_m else None

        since_m = re.search(r"member since.*?<dd[^>]*>\s*([^<]+)", html, re.I | re.S)
        member_since = since_m.group(1).strip() if since_m else None

        result = {
            "site": "Wikidot",
            "username": args.username,
            "display_name": display_name,
            "user_id": user_id,
            "avatar_url": avatar_url,
            "karma": karma,
            "member_since": member_since,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
