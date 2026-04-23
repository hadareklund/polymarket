#!/usr/bin/env python3
"""Fetch user profile information from Sketchfab (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Sketchfab user info by username.")
    parser.add_argument("username", help="Sketchfab username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://sketchfab.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        og_desc = _meta(html, "og:description", attr="property")

        # Extract display name and @handle from og:title format "Display Name (@handle)"
        display_name = None
        if og_title:
            m = re.match(r"^(.+?)\s+\(@\S+\)$", og_title)
            display_name = m.group(1).strip() if m else og_title

        # Avatar is embedded in the React bundle (no og:image served)
        avatar_m = re.search(
            r"https?://media\.sketchfab\.com/avatars/[a-f0-9]+/[a-f0-9]+\.jpe?g", html
        )
        avatar_url = avatar_m.group(0) if avatar_m else None

        result = {
            "site": "Sketchfab",
            "username": args.username,
            "display_name": display_name,
            "bio": og_desc,
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
