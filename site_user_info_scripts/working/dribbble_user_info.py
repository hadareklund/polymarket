#!/usr/bin/env python3
"""Fetch user profile information from Dribbble (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Dribbble user info by username.")
    parser.add_argument("username", help="Dribbble username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://dribbble.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        og_image = _meta(html, "og:image", attr="property")
        description = _meta(html, "description")
        twitter_handle = _meta(html, "twitter:creator")

        # Not found pages have generic titles
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else ""
        if "page not found" in page_title.lower() or "dribbble - discover" == page_title.lower():
            raise RuntimeError(f"User '{args.username}' not found on Dribbble.")

        # Description format: "Name | bio | Connect with them on Dribbble..."
        bio = None
        if description:
            parts = description.split(" | ")
            if len(parts) >= 2:
                # Strip the trailing "Connect with them on Dribbble..." part
                bio_parts = [p for p in parts[1:] if "Connect with them on Dribbble" not in p]
                bio = " | ".join(bio_parts).strip() or None

        result = {
            "site": "Dribbble",
            "username": args.username,
            "name": og_title,
            "bio": bio,
            "twitter": twitter_handle.lstrip("@") if twitter_handle else None,
            "avatar_url": og_image,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
