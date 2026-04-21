#!/usr/bin/env python3
"""Fetch user profile information from CodePen (HTML scraper)."""

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


def _unescape(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&#39;", "'").replace("&quot;", '"')
    return s


def main() -> int:
    parser = argparse.ArgumentParser(description="Get CodePen user info by username.")
    parser.add_argument("username", help="CodePen username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://codepen.io/{args.username}"
        html = fetch_text(url, headers={"User-Agent": _UA}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else None
        if title and "404" in title:
            raise RuntimeError(f"User not found: {args.username!r}")

        display_name = _meta(html, "og:title", "property") or title
        if display_name:
            # Strip trailing " on CodePen"
            display_name = re.sub(r"\s+on CodePen\s*$", "", display_name).strip()

        bio_raw = _meta(html, "og:description", "property") or _meta(html, "description")
        bio = _unescape(bio_raw) if bio_raw else None

        avatar_raw = _meta(html, "og:image", "property")
        avatar_url = _unescape(avatar_raw) if avatar_raw else None

        # Follower / following counts embedded in the page
        followers_m = re.search(r'"followers_count"\s*:\s*(\d+)', html)
        following_m = re.search(r'"following_count"\s*:\s*(\d+)', html)
        pens_m = re.search(r'"pens_count"\s*:\s*(\d+)', html)

        # Location
        location_m = re.search(r'"location"\s*:\s*"([^"]+)"', html)

        result = {
            "site": "CodePen",
            "username": args.username,
            "display_name": display_name,
            "bio": bio,
            "location": location_m.group(1) if location_m else None,
            "followers": int(followers_m.group(1)) if followers_m else None,
            "following": int(following_m.group(1)) if following_m else None,
            "pens_count": int(pens_m.group(1)) if pens_m else None,
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
