#!/usr/bin/env python3
"""Fetch user profile information from SpeakerDeck (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _extract(pattern: str, html: str, group: int = 1) -> str | None:
    m = re.search(pattern, html, re.I | re.S)
    return m.group(group).strip() if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get SpeakerDeck user info by username.")
    parser.add_argument("username", help="SpeakerDeck username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://speakerdeck.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        raw_title = title_m.group(1).strip() if title_m else ""
        # Title format: "Display Name (@username) on Speaker Deck"
        display_name_m = re.match(r"^(.+?)\s+\(@[^)]+\)", raw_title)
        display_name = display_name_m.group(1).strip() if display_name_m else None

        bio_m = re.search(r'class="profile--description">\s*<p>(.*?)</p>', html, re.I | re.S)
        bio = re.sub(r"<[^>]+>", "", bio_m.group(1)).strip() if bio_m else None

        followers_m = re.search(r"(\d+)\s+Followers", html)
        following_m = re.search(r"(\d+)\s+Following", html)
        stars_m = re.search(r"(\d+)\s+Stars", html)

        # Get highest-resolution gravatar avatar
        avatar_m = re.search(r'(https://secure\.gravatar\.com/avatar/[a-f0-9]+)\?', html)
        avatar_url = f"{avatar_m.group(1)}?s=200" if avatar_m else None

        result = {
            "site": "SpeakerDeck",
            "username": args.username,
            "display_name": display_name,
            "bio": bio,
            "followers": int(followers_m.group(1)) if followers_m else None,
            "following": int(following_m.group(1)) if following_m else None,
            "stars": int(stars_m.group(1)) if stars_m else None,
            "avatar_url": avatar_url,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
