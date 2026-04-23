#!/usr/bin/env python3
"""Fetch user profile information from Facebook (OG meta scraper — public pages only)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _meta(html: str, name: str, attr: str = "property") -> str | None:
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
        description="Get Facebook public page/profile info by username."
    )
    parser.add_argument("username", help="Facebook username or page slug")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.facebook.com/{args.username}"
        html = fetch_text(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
            },
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title")
        og_description = _meta(html, "og:description")
        og_image = _meta(html, "og:image")
        og_url = _meta(html, "og:url")

        if not og_title:
            raise RuntimeError(f"No public profile data found for '{args.username}' — may be private or non-existent.")

        # Clean HTML entities from description
        description = og_description
        if description:
            description = re.sub(r"&#xa0;", " ", description)
            description = re.sub(r"&#x[0-9a-f]+;", "", description, flags=re.I)

        result = {
            "site": "Facebook",
            "username": args.username,
            "name": og_title,
            "description": description,
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
