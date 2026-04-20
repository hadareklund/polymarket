#!/usr/bin/env python3
"""Fetch user profile information from Itch.io."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Itch.io user info by username.")
    parser.add_argument("username", help="Itch.io username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://itch.io/api/1/x/whoami", timeout=args.timeout)
        # Itch.io has no public user profile API — falls back to HTML scraping.
        from common import fetch_text
        import re as _re
        html = fetch_text(f"https://{args.username}.itch.io", headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        title_m = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.I)
        desc_m = _re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, _re.I)
        result = {
            "site": "Itch.io",
            "username": args.username,
            "title": title_m.group(1).strip() if title_m else None,
            "description": desc_m.group(1).strip() if desc_m else None,
            "profile_url": f"https://{args.username}.itch.io",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
