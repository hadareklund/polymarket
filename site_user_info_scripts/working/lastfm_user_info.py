#!/usr/bin/env python3
"""Fetch user profile information from Last.fm (HTML scraper, no API key required)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _og(html: str, prop: str) -> str | None:
    for pat in [
        rf'<meta[^>]+property="og:{re.escape(prop)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="og:{re.escape(prop)}"',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Last.fm user info by username.")
    parser.add_argument("username", help="Last.fm username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.last.fm/user/{args.username}"
        html = fetch_text(url, headers=_HEADERS, timeout=args.timeout)
        if "Rate Limited" in html or len(html) < 1000:
            raise RuntimeError("Rate limited or empty response from Last.fm.")

        # og:description: "Listen to music from {Name}'s library ({N} tracks played)..."
        desc = _og(html, "description") or ""
        og_title = _og(html, "title") or ""
        avatar_url = _og(html, "image")

        # Display name from description: "Listen to music from X's library (N tracks played)"
        # Last.fm uses Unicode right-single-quote (’) not a plain apostrophe.
        display_name = None
        m = re.search(r"Listen to music from (.+?)[’'s]+\s+library", desc)
        if m:
            display_name = m.group(1).strip()
        elif og_title:
            # og:title: "Username’s Music Profile | Last.fm"
            m = re.match(r"^(.+?)[’'s]+\s+Music Profile", og_title)
            if not m:
                m = re.match(r"^(.+?)\s*\|", og_title)
            display_name = m.group(1).strip() if m else None

        # Scrobble count from description: "N tracks played"
        scrobbles = None
        m = re.search(r"([\d,]+)\s+tracks?\s+played", desc, re.I)
        if m:
            scrobbles = int(m.group(1).replace(",", ""))

        result = {
            "site": "Last.fm",
            "username": args.username,
            "display_name": display_name,
            "scrobbles": scrobbles,
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
