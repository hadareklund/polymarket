#!/usr/bin/env python3
"""Fetch user profile information from SoundCloud (HTML scraper)."""

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


def _int(html: str, key: str) -> int | None:
    m = re.search(rf'"{re.escape(key)}":(\d+)', html)
    return int(m.group(1)) if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get SoundCloud user info by username.")
    parser.add_argument("username", help="SoundCloud username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://soundcloud.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        og_desc = _meta(html, "og:description", attr="property")
        og_image = _meta(html, "og:image", attr="property")

        result = {
            "site": "SoundCloud",
            "username": args.username,
            "display_name": og_title,
            "bio": og_desc,
            "avatar_url": og_image,
            "followers_count": _int(html, "followers_count"),
            "track_count": _int(html, "track_count"),
            "playlist_count": _int(html, "playlist_count"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
