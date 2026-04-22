#!/usr/bin/env python3
"""Fetch user profile information from Couchsurfing (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _meta(html: str, name: str, attr: str = "name") -> str | None:
    for pattern in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Couchsurfing user info by username.")
    parser.add_argument("username", help="Couchsurfing username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.couchsurfing.com/people/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        og_image = _meta(html, "og:image", attr="property")
        og_url = _meta(html, "og:url", attr="property")

        # Not found page check
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else ""
        if "not found" in page_title.lower() or "error" in page_title.lower():
            raise RuntimeError(f"User '{args.username}' not found on Couchsurfing.")

        # Location appears in a sidebar link
        location_m = re.search(
            r'class="profile-sidebar__city[^"]*"[^>]*>\s*([^<\n]+?)\s*</a>', html
        )
        location = location_m.group(1).strip() if location_m else None

        # Occupation
        occupation_m = re.search(r'class="[^"]*mod-occupation[^"]*"[^>]*>\s*([^<\n]+?)\s*<', html)
        occupation = occupation_m.group(1).strip() if occupation_m else None
        if occupation and occupation.lower() in ("no occupation listed", ""):
            occupation = None

        result = {
            "site": "Couchsurfing",
            "username": args.username,
            "name": og_title,
            "location": location,
            "occupation": occupation,
            "avatar_url": og_image,
            "profile_url": og_url or url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
