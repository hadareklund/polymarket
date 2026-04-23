#!/usr/bin/env python3
"""Fetch user profile information from Flickr (HTML scraper, no API key required)."""

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
    parser = argparse.ArgumentParser(
        description="Get Flickr user info by username or NSID (no API key required)."
    )
    parser.add_argument("username", help="Flickr username or path alias")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.flickr.com/people/{args.username}/"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else ""
        if "page not found" in page_title.lower() or "flickr" not in page_title.lower():
            raise RuntimeError(f"User '{args.username}' not found on Flickr.")

        display_name = _meta(html, "og:title", attr="property")
        description = _meta(html, "description")

        # NSID embedded in HTML (e.g. 51035555243@N01)
        nsid_m = re.search(r'"nsid"\s*:\s*"([0-9]+@N[0-9]+)"', html)
        nsid = nsid_m.group(1) if nsid_m else None

        # Avatar: Flickr redirects /buddyicons/{nsid}.jpg to the real farm URL
        avatar_url = f"https://www.flickr.com/buddyicons/{nsid}.jpg" if nsid else None

        # Photo count: "353,112 Photos" in the page body
        count_m = re.search(r"([\d,]+)\s*Photos", html, re.I)
        photo_count = count_m.group(1).replace(",", "") if count_m else None

        # Location from a dedicated element (first non-regex location class match)
        loc_m = re.search(
            r'class="[^"]*location[^"]*"[^>]*>\s*<[^>]+>\s*([^<]{2,80}?)\s*<', html, re.I
        )
        location = loc_m.group(1).strip() if loc_m else None

        result = {
            "site": "Flickr",
            "username": args.username,
            "display_name": display_name,
            "bio": description,
            "location": location,
            "nsid": nsid,
            "photo_count": int(photo_count) if photo_count and photo_count.isdigit() else None,
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
