#!/usr/bin/env python3
"""Fetch user profile information from Coderwall (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Coderwall user info by username.")
    parser.add_argument("username", help="Coderwall username (case-sensitive)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://coderwall.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        if og_title and "404" in og_title:
            raise RuntimeError(f"User '{args.username}' not found on Coderwall.")

        og_desc = _meta(html, "og:description", attr="property")
        og_image = _meta(html, "og:image", attr="property")
        og_url = _meta(html, "og:url", attr="property")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else None

        name = None
        if og_title:
            # og:title format: "Name&#39;s profile | username" or "Name's profile | username"
            m = re.match(r"^(.+?)(?:&#\d+;s profile|'s profile)", og_title)
            if m:
                name = m.group(1).strip()

        result = {
            "site": "Coderwall",
            "username": args.username,
            "name": name,
            "description": og_desc,
            "avatar_url": og_image,
            "profile_url": f"https://coderwall.com{og_url}" if og_url and og_url.startswith("/") else url,
            "page_title": page_title,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
