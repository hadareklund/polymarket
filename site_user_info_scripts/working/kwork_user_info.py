#!/usr/bin/env python3
"""Fetch user profile information from Kwork (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get Kwork user info by username.")
    parser.add_argument("username", help="Kwork username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://kwork.ru/user/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Title format: "Фрилансер DisplayName (Username)  - Kwork"
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        display_name = None
        if title_m:
            name_m = re.match(r"Фрилансер\s+(.+?)\s*-\s*Kwork", title_m.group(1).strip(), re.I)
            if name_m:
                display_name = name_m.group(1).strip()

        result = {
            "site": "Kwork",
            "username": args.username,
            "display_name": display_name,
            "description": _meta(html, "description"),
            "avatar_url": _meta(html, "og:image", attr="property"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
