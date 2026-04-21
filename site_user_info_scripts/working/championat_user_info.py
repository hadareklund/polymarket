#!/usr/bin/env python3
"""Fetch user profile information from Championat.com (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
)


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
    parser = argparse.ArgumentParser(description="Get Championat user info by username.")
    parser.add_argument("username", help="Championat username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.championat.com/user/{args.username}/"
        html = fetch_text(
            url,
            headers={"User-Agent": _UA, "Accept-Language": "ru,en;q=0.9"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", "property")
        # og:title is "Личный профиль {username}" — extract the username part
        # If the page doesn't have a real user profile the title won't match
        if not og_title or args.username.lower() not in og_title.lower():
            title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
            title = title_m.group(1).strip() if title_m else ""
            if args.username.lower() not in title.lower():
                raise RuntimeError(f"User not found: {args.username!r}")

        # Extract display name from the profile name element in the page body
        name_m = re.search(
            r'class="[^"]*profile[^"]*name[^"]*"[^>]*>\s*([^\s<][^<]*?)\s*<',
            html,
            re.I,
        )
        display_name = name_m.group(1).strip() if name_m else args.username

        # Avatar URL embedded in the page (user-specific img tag near profile section)
        avatar_m = re.search(
            r'class="[^"]*userpic[^"]*"[^>]*src="([^"]+)"', html, re.I
        )
        if not avatar_m:
            avatar_m = re.search(
                r'src="([^"]+)"[^>]*class="[^"]*userpic[^"]*"', html, re.I
            )
        avatar_url = avatar_m.group(1) if avatar_m else None

        result = {
            "site": "Championat",
            "username": args.username,
            "display_name": display_name,
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
