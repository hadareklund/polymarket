#!/usr/bin/env python3
"""Fetch user profile information from Crowdin (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Crowdin user info by username.")
    parser.add_argument("username", help="Crowdin username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://crowdin.com/profile/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        page_title = title_m.group(1).strip() if title_m else ""

        if "not found" in page_title.lower() or "page not found" in page_title.lower():
            raise RuntimeError(f"User '{args.username}' not found on Crowdin.")

        # Title format: "FullName (username) – Crowdin"
        full_name = None
        parsed_username = None
        title_parsed = re.match(r"^(.+?)\s*\(([^)]+)\)\s*[–\-]", page_title)
        if title_parsed:
            full_name = title_parsed.group(1).strip()
            parsed_username = title_parsed.group(2).strip()

        # Description: "Name's Profile on crowdin.com. ..."
        desc_m = re.search(r'<meta\s[^>]*name="description"[^>]*content="([^"]*)"', html, re.I)
        description = desc_m.group(1).strip() if desc_m else None

        result = {
            "site": "Crowdin",
            "username": parsed_username or args.username,
            "name": full_name,
            "description": description,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
