#!/usr/bin/env python3
"""Fetch user profile information from Untappd (HTML scraper)."""

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


def _text(html: str, pattern: str) -> str | None:
    m = re.search(pattern, html, re.I | re.DOTALL)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip() or None
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Untappd user info by username.")
    parser.add_argument("username", help="Untappd username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://untappd.com/user/{args.username}"
        html = fetch_text(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title_text = title_m.group(1).strip() if title_m else ""
        if "404" in title_text or not title_text:
            raise RuntimeError(f"User '{args.username}' not found on Untappd.")

        is_private = "private_user" in html and "set their account to be private" in html

        # Display name and username from the profile header info block
        display_name = _text(html, r'class="info"[^>]*>.*?<h1>\s*(.*?)\s*</h1>')
        uname = _text(html, r'<p class="username">\s*([^<]+)\s*</p>') or args.username
        location = _text(html, r'<p class="location">\s*([^<]+)\s*</p>')

        # Stats: Total checkins, Unique beers, Badges, Friends
        stat_pairs = re.findall(
            r'<span class="stat">([\d,]+)</span>\s*<span class="title">([^<]+)</span>', html
        )
        stats = {label.strip(): val.replace(",", "") for val, label in stat_pairs}

        # Avatar: first non-gravatar/default img after profile-header section
        avatar_m = re.search(
            r'<a[^>]+class="[^"]*profile-pic[^"]*"[^>]*>\s*<img[^>]+src="([^"]+)"', html, re.I | re.DOTALL
        )
        if not avatar_m:
            avatar_m = re.search(r'<img[^>]+src="(https://[^"]+(?:gravatar|untappd)[^"]+)"', html, re.I)
        avatar_url = avatar_m.group(1) if avatar_m else _meta(html, "og:image", "property")

        # User ID
        uid_m = re.search(r'data-user-id="(\d+)"', html)

        result = {
            "site": "Untappd",
            "username": uname,
            "display_name": display_name,
            "location": location,
            "is_private": is_private,
            "total_checkins": stats.get("Total"),
            "unique_beers": stats.get("Unique"),
            "badges": stats.get("Badges"),
            "friends": stats.get("Friends"),
            "user_id": uid_m.group(1) if uid_m else None,
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
