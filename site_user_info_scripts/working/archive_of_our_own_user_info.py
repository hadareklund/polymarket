#!/usr/bin/env python3
"""Fetch user profile information from Archive of Our Own (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Archive of Our Own user info by username.")
    parser.add_argument("username", help="AO3 username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://archiveofourown.org/users/{args.username}/profile"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        h2_m = re.search(r"<h2[^>]*>\s*([^<\s][^<]*?)\s*</h2>", html, re.I)

        bio_m = re.search(
            r'class="bio module".*?<blockquote[^>]*>(.*?)</blockquote>', html, re.S | re.I
        )
        bio_text = re.sub(r"<[^>]+>", "", bio_m.group(1)).strip() if bio_m else None

        works_m = re.search(r"Works \((\d+)\)", html)
        bookmarks_m = re.search(r"Bookmarks \((\d+)\)", html)

        meta_pairs = re.findall(r"<dt[^>]*>([^<]+)</dt>\s*<dd[^>]*>([^<]+)</dd>", html)
        joined = next((v.strip() for k, v in meta_pairs if "joined" in k.lower()), None)
        user_id = next((v.strip() for k, v in meta_pairs if "user id" in k.lower()), None)

        result = {
            "site": "Archive of Our Own",
            "username": args.username,
            "display_name": h2_m.group(1).strip() if h2_m else None,
            "bio": bio_text,
            "works_count": int(works_m.group(1)) if works_m else None,
            "bookmarks_count": int(bookmarks_m.group(1)) if bookmarks_m else None,
            "joined": joined,
            "user_id": user_id,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
