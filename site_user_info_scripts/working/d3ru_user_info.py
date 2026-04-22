#!/usr/bin/env python3
"""Fetch user profile information from D3.ru (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get D3.ru user info by username.")
    parser.add_argument("username", help="D3.ru username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://d3.ru/user/{args.username}/"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else ""

        # Title format: "d3.ru — username"; 404 page has different title
        if args.username not in page_title:
            raise RuntimeError(f"User '{args.username}' not found on D3.ru.")

        # Full name
        full_name_m = re.search(r'class="b-user_full_name">([^<]+)<', html)
        full_name = full_name_m.group(1).strip() if full_name_m else None

        # Location / residence
        residence_m = re.search(r'class="b-user_residence">([^<]*)<', html)
        residence = residence_m.group(1).strip() if residence_m else None
        if not residence:
            residence = None

        # Karma value
        karma_m = re.search(r'class="b-karma_value"[^>]*>([^<]+)<', html)
        karma = karma_m.group(1).strip() if karma_m else None
        try:
            karma = int(karma) if karma else None
        except ValueError:
            pass

        # Internal user_id
        uid_m = re.search(r'data-user_id="(\d+)"', html)
        user_id = uid_m.group(1) if uid_m else None

        result = {
            "site": "D3.ru",
            "username": args.username,
            "name": full_name,
            "location": residence,
            "karma": karma,
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
