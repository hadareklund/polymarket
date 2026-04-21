#!/usr/bin/env python3
"""Fetch user profile information from Naver Blog."""

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
        rf"property=\"{re.escape(name)}\"[^>]+content=\"([^\"]+)\"",
        rf"content=\"([^\"]+)\"[^>]+property=\"{re.escape(name)}\"",
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Naver Blog user info by username.")
    parser.add_argument("username", help="Naver Blog username (blogId)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://m.blog.naver.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response — user may not exist.")
        title = _meta(html, "og:title", "property")
        description = _meta(html, "og:description", "property")
        avatar_url = _meta(html, "og:image", "property")
        result = {
            "site": "Naver Blog",
            "username": args.username,
            "title": title,
            "description": description,
            "avatar_url": avatar_url,
            "profile_url": f"https://blog.naver.com/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
