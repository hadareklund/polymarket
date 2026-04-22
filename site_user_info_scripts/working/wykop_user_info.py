#!/usr/bin/env python3
"""Fetch Wykop.pl user profile info via HTML OG tag scraping."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"


def _meta_og(html: str, prop: str) -> str | None:
    m = re.search(
        rf'property="{re.escape(prop)}"\s+content="([^"]*)"', html, re.I
    ) or re.search(
        rf'content="([^"]*)"\s+[^>]*property="{re.escape(prop)}"', html, re.I
    )
    return m.group(1).strip() if m else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Wykop.pl user info by username.")
    parser.add_argument("username", help="Wykop username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    url = f"https://www.wykop.pl/ludzie/{args.username}/"
    try:
        html = fetch_text(
            url,
            headers={"User-Agent": UA, "Accept-Language": "pl,en;q=0.9"},
            timeout=args.timeout,
        )
        title = _meta_og(html, "og:title")
        description = _meta_og(html, "og:description")
        if not title or "Profil:" not in title:
            raise RuntimeError(f"User '{args.username}' not found or unexpected page.")
        result = {
            "site": "Wykop",
            "username": args.username,
            "profile_title": title,
            "profile_description": description,
            "profile_url": f"https://wykop.pl/ludzie/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
