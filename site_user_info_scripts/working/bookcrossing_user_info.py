#!/usr/bin/env python3
"""Fetch user profile information from Bookcrossing (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Bookcrossing user info by username.")
    parser.add_argument("username", help="Bookcrossing username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.bookcrossing.com/mybookshelf/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else None
        if title and ("Page Not Found" in title or "404" in title):
            raise RuntimeError(f"User not found: {args.username!r}")

        display_name = _meta(html, "og:title", "property") or title
        description = _meta(html, "description")
        avatar_url = _meta(html, "og:image", "property")

        # Books registered / released / caught from the shelf page stats
        books_m = re.search(r"(\d+)\s+book(?:s)?\s+registered", html, re.I)
        released_m = re.search(r"(\d+)\s+book(?:s)?\s+released", html, re.I)

        result = {
            "site": "Bookcrossing",
            "username": args.username,
            "display_name": display_name,
            "description": description,
            "books_registered": int(books_m.group(1)) if books_m else None,
            "books_released": int(released_m.group(1)) if released_m else None,
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
