#!/usr/bin/env python3
"""Fetch user profile information from Blitz Tactics (HTML scraper).

Blitz Tactics profile URLs use /{username} (not /users/{username}).
"""

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
    parser = argparse.ArgumentParser(description="Get Blitz Tactics user info by username.")
    parser.add_argument("username", help="Blitz Tactics username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://blitztactics.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        if title_m and "Blitz Tactics" in title_m.group(1) and "|" not in title_m.group(1):
            raise RuntimeError(f"User profile not found for {args.username!r}")

        member_since_m = re.search(r'class="member-since"[^>]*>Member since ([^<]+)<', html)
        unique_m = re.search(
            r'Unique puzzles solved.*?<div class="count">(\d+)</div>', html, re.S
        )

        # Collect all stats-row labels + counts
        rows = re.findall(
            r'<div class="long-label">([^<]+)</div>\s*<div class="count">([^<]+)</div>', html
        )
        stats = {label.strip(): val.strip() for label, val in rows}

        result = {
            "site": "Blitz Tactics",
            "username": args.username,
            "member_since": member_since_m.group(1).strip() if member_since_m else None,
            "unique_puzzles_solved": int(unique_m.group(1)) if unique_m else None,
            "stats": stats,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
