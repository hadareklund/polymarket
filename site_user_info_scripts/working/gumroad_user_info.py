#!/usr/bin/env python3
"""Fetch user profile information from Gumroad (HTML scraper)."""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Gumroad user info by username.")
    parser.add_argument("username", help="Gumroad username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        url = f"https://gumroad.com/{args.username}"
        page = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(page) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Inertia.js embeds page props as HTML-entity-encoded JSON in data-page attr
        m = re.search(r'data-page="([^"]+)"', page)
        if not m:
            raise RuntimeError("Could not find data-page attribute.")
        props = json.loads(html_mod.unescape(m.group(1))).get("props", {})

        cp = props.get("creator_profile") or {}
        result = {
            "site": "Gumroad",
            "username": args.username,
            "name": cp.get("name") or props.get("name"),
            "bio": props.get("bio"),
            "avatar_url": cp.get("avatar_url"),
            "twitter_handle": cp.get("twitter_handle"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
