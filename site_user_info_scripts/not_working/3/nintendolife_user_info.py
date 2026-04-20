#!/usr/bin/env python3
"""Fetch user profile information from Nintendo Life (HTML scraper)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json

import re


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Nintendo Life user info by username.")
    parser.add_argument("username", help="Nintendo Life username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        from common import fetch_text
        url = f"https://www.nintendolife.com/users/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        desc_m = re.search(r'<meta[^>]+name=["']description["'][^>]+content=["']([^"']+)', html, re.I)
        og_title = re.search(r'<meta[^>]+property=["']og:title["'][^>]+content=["']([^"']+)', html, re.I)
        og_image = re.search(r'<meta[^>]+property=["']og:image["'][^>]+content=["']([^"']+)', html, re.I)
        result = {
            "site": "Nintendo Life",
            "username": args.username,
            "title": og_title.group(1).strip() if og_title else (title_m.group(1).strip() if title_m else None),
            "description": desc_m.group(1).strip() if desc_m else None,
            "avatar_url": og_image.group(1).strip() if og_image else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
