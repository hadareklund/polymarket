#!/usr/bin/env python3
"""Fetch user profile information from Pastebin (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Pastebin user info by username.")
    parser.add_argument("username", help="Pastebin username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://pastebin.com/u/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        if "Not Found" in html[:2000] or "404" in html[:500]:
            raise RuntimeError("User not found.")

        # Display name from h1 inside user-view
        m_name = re.search(r'class="user-view".*?<h1>([^<]+)</h1>', html, re.S)
        display_name = m_name.group(1).strip() if m_name else None

        # Avatar
        m_avatar = re.search(r'class="user-icon"[^>]*>.*?<img\s+src="([^"]+)"', html, re.S)
        avatar_url = m_avatar.group(1) if m_avatar else None
        if avatar_url and avatar_url.startswith("/"):
            avatar_url = "https://pastebin.com" + avatar_url

        # Page-view count (profile page views)
        m_views = re.search(r'<span class="views"[^>]*>([^<]+)</span>', html)
        profile_views = m_views.group(1).strip().replace(",", "") if m_views else None

        # Join date title attribute
        m_date = re.search(r'<span class="date-text"[^>]*title="([^"]+)"', html)
        joined = m_date.group(1) if m_date else None

        # Count public pastes listed on the page
        paste_links = re.findall(r'href="/[A-Za-z0-9]{8}"', html)
        paste_count_page = len(paste_links)

        result = {
            "site": "Pastebin",
            "username": args.username,
            "display_name": display_name,
            "avatar_url": avatar_url,
            "profile_views": int(profile_views) if profile_views and profile_views.isdigit() else None,
            "joined": joined,
            "public_pastes_on_page": paste_count_page if paste_count_page else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
