#!/usr/bin/env python3
"""Fetch user profile information from Warrior Forum (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Warrior Forum user info by username.")
    parser.add_argument("username", help="Warrior Forum username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.warriorforum.com/members/{args.username}.html"
        html = fetch_text(url, headers={"User-Agent": UA}, timeout=args.timeout)
        if len(html) < 500 or "Oops" in html[:2000]:
            raise RuntimeError("User not found or empty response.")

        h1_m = re.search(r"<h1[^>]*>([^<']+)'s Profile", html, re.I)
        display_name = h1_m.group(1).strip() if h1_m else args.username

        av_m = re.search(r'src="(https://assets\.warriorforum\.com/avatar/[^"]+)"', html)
        avatar_url = av_m.group(1) if av_m else None

        join_m = re.search(r"Join Date:</span>\s*([^<]+)", html)
        join_date = join_m.group(1).strip() if join_m else None

        posts_m = re.search(r"Total Posts:</span>\s*(\d[\d,]*)", html)
        posts = int(posts_m.group(1).replace(",", "")) if posts_m else None

        result = {
            "site": "Warrior Forum",
            "username": args.username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "join_date": join_date,
            "total_posts": posts,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
