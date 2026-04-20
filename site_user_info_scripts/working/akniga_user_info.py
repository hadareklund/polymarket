#!/usr/bin/env python3
"""Fetch user profile information from Akniga.org (HTML scraper)."""

from __future__ import annotations

import argparse
import json
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


def _json_ld(html: str) -> dict:
    m = re.search(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.I | re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Akniga user info by username.")
    parser.add_argument("username", help="Akniga username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        url = f"https://akniga.org/profile/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        ld = _json_ld(html)
        title_tag = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)

        # Akniga profile pages embed book count / review count in the page body
        books_m = re.search(r'(\d+)\s*(?:книг|аудиокниг)', html, re.I)
        reviews_m = re.search(r'(\d+)\s*(?:отзыв|рецензи)', html, re.I)

        result = {
            "site": "Akniga",
            "username": args.username,
            "name": ld.get("name") or _meta(html, "og:title", "property"),
            "description": ld.get("description") or _meta(html, "description") or _meta(html, "og:description", "property"),
            "avatar_url": ld.get("image") or _meta(html, "og:image", "property"),
            "book_count": int(books_m.group(1)) if books_m else None,
            "review_count": int(reviews_m.group(1)) if reviews_m else None,
            "title": title_tag.group(1).strip() if title_tag else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
