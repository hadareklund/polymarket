#!/usr/bin/env python3
"""Fetch user profile information from Ultimate Guitar (JSON-LD scraper)."""

from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _jsonld(html: str) -> dict:
    m = re.search(r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', html, re.DOTALL | re.I)
    if m:
        try:
            return _json.loads(m.group(1))
        except Exception:
            pass
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Ultimate Guitar user info by username.")
    parser.add_argument("username", help="Ultimate Guitar username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.ultimate-guitar.com/u/{args.username}"
        html = fetch_text(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                )
            },
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title_text = title_m.group(1).strip() if title_m else ""
        if "404" in title_text or "Not Found" in title_text:
            raise RuntimeError(f"User '{args.username}' not found on Ultimate Guitar.")

        ld = _jsonld(html)
        entity = ld.get("mainEntity", {})
        interaction = entity.get("interactionStatistic", {})

        result = {
            "site": "Ultimate Guitar",
            "username": entity.get("alternateName") or args.username,
            "display_name": entity.get("name") or None,
            "user_id": entity.get("identifier"),
            "avatar_url": entity.get("image"),
            "followers": interaction.get("userInteractionCount"),
            "joined": ld.get("dateCreated"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
