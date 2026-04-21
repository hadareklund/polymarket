#!/usr/bin/env python3
"""Fetch user/blog profile information from Tumblr (HTML scraper).

Tumblr blogs are hosted at {username}.tumblr.com.
"""

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
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


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
    parser = argparse.ArgumentParser(description="Get Tumblr blog info by username.")
    parser.add_argument("username", help="Tumblr blog username (subdomain)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://{args.username}.tumblr.com"
        html = fetch_text(url, headers=_HEADERS, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        result = {
            "site": "Tumblr",
            "username": args.username,
            "blog_title": _meta(html, "og:title", "property") or (title_m.group(1).strip() if title_m else None),
            "description": _meta(html, "og:description", "property") or _meta(html, "description"),
            "avatar_url": _meta(html, "og:image", "property"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
