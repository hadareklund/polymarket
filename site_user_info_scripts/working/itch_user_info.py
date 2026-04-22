#!/usr/bin/env python3
"""Fetch user profile information from Itch.io (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Itch.io user info by username.")
    parser.add_argument("username", help="Itch.io username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://{args.username}.itch.io"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Display name from twitter:title meta tag
        m = re.search(r'<meta name="twitter:title" content="([^"]+)"', html)
        display_name = m.group(1).strip() if m else args.username

        # Bio from short_bio section
        bio = None
        m = re.search(r'class="short_bio"[^>]*>(.*?)</div>', html, re.S)
        if m:
            bio = re.sub(r"<[^>]+>", "", m.group(1)).strip() or None

        # Profile banner image — src precedes class in itch.io HTML
        banner_url = None
        m = re.search(r'<img[^>]+src="([^"]+)"[^>]+class="profile_banner"', html)
        if m:
            banner_url = m.group(1)

        # Count games — each game card has class "game_cell has_cover"
        game_count = len(re.findall(r'class="game_cell has_cover', html))

        result = {
            "site": "Itch.io",
            "username": args.username,
            "display_name": display_name,
            "bio": bio,
            "banner_url": banner_url,
            "games_listed": game_count if game_count else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
