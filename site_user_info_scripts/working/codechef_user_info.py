#!/usr/bin/env python3
"""Fetch user profile information from CodeChef (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get CodeChef user info by username.")
    parser.add_argument("username", help="CodeChef username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.codechef.com/users/{args.username}"
        html = fetch_text(url, headers={"User-Agent": _UA}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", "property") or ""
        if "User Profile" not in og_title and args.username.lower() not in og_title.lower():
            raise RuntimeError(f"User not found: {args.username!r}")

        # Current rating from the rating-number div
        rating_m = re.search(r'<div[^>]*class="rating-number"[^>]*>\s*(\d+)', html, re.I)
        rating = int(rating_m.group(1)) if rating_m else None

        # Star count from the inline rating span
        stars_m = re.search(r"class='rating'[^>]*>(\d+)&#9733;", html)
        stars = int(stars_m.group(1)) if stars_m else None

        # Global rank from og:title "global rank X"
        rank_m = re.search(r"global rank\s+(\d+)", og_title, re.I)
        global_rank = int(rank_m.group(1)) if rank_m else None

        # Profile fields from the user-details side nav
        country_m = re.search(r'<span class="user-country-name"[^>]*>([^<]+)</span>', html, re.I)
        inst_m = re.search(r"<label>Institution:</label><span>([^<]+)</span>", html, re.I)
        role_m = re.search(r"<label>Student/Professional:</label><span>([^<]+)</span>", html, re.I)

        result = {
            "site": "CodeChef",
            "username": args.username,
            "rating": rating,
            "stars": stars,
            "global_rank": global_rank,
            "country": country_m.group(1).strip() if country_m else None,
            "institution": inst_m.group(1).strip() if inst_m else None,
            "role": role_m.group(1).strip() if role_m else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
