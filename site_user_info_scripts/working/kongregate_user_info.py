#!/usr/bin/env python3
"""Fetch user profile information from Kongregate (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _extract_stat(html: str, username: str, stat_name: str) -> int | None:
    pattern = (
        rf'accounts/{re.escape(username)}/{re.escape(stat_name.lower())}">'
        r'.*?<div[^>]*>([\d,]+)</div>.*?<div[^>]*>'
        + re.escape(stat_name) + r'</div>'
    )
    m = re.search(pattern, html, re.DOTALL | re.I)
    if m:
        return int(m.group(1).replace(',', ''))
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Kongregate user info by username.")
    parser.add_argument("username", help="Kongregate username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.kongregate.com/accounts/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        display_name = None
        if title_m:
            raw_title = title_m.group(1).strip().replace("&#39;", "'").replace("&amp;", "&")
            name_m = re.match(r"(.+?)'s profile on Kongregate", raw_title, re.I)
            if name_m:
                display_name = name_m.group(1).strip()

        level_m = re.search(r'levelbug level_(\d+)', html, re.I)
        level = int(level_m.group(1)) if level_m else None

        avatar_m = re.search(
            rf'alt="avatar for {re.escape(args.username)}"[^>]+src="([^"]+)"',
            html, re.I,
        )
        avatar_url = avatar_m.group(1) if avatar_m else None

        # Points uses a different CSS class than the other stats
        points_m = re.search(
            r'<div[^>]*text-xl font-bold[^>]*>([\d,]+)</div>\s*<div[^>]*>Points</div>',
            html, re.I,
        )
        points = int(points_m.group(1).replace(',', '')) if points_m else None

        result = {
            "site": "Kongregate",
            "username": args.username,
            "display_name": display_name,
            "level": level,
            "points": points,
            "badges": _extract_stat(html, args.username, "Badges"),
            "fans": _extract_stat(html, args.username, "Fans"),
            "friends": _extract_stat(html, args.username, "Friends"),
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
