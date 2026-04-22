#!/usr/bin/env python3
"""Fetch user profile information from Product Hunt (relay cache scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _field(html: str, key: str) -> str | None:
    """Extract a string, numeric, or boolean field from a relay cache block."""
    m = re.search(rf'"{re.escape(key)}"\s*:\s*("((?:[^"\\]|\\.)*)"|(\d+)|(true|false)|null)', html)
    if not m:
        return None
    if m.group(2) is not None:
        # Decode JSON unicode escapes in string values
        try:
            import json
            return json.loads(f'"{m.group(2)}"')
        except Exception:
            return m.group(2)
    if m.group(3) is not None:
        return m.group(3)
    if m.group(4) is not None:
        return m.group(4)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Product Hunt user info by username.")
    parser.add_argument("username", help="Product Hunt username (without @)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.producthunt.com/@{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Find the relay cache block that contains the user profile
        profile_start = html.find('"profile":{"__typename":"User"')
        if profile_start == -1:
            raise RuntimeError("Could not find profile data in page.")

        block = html[profile_start : profile_start + 2000]

        # username must match what we requested to avoid false positives from viewer object
        username_in_block = _field(block, "username")
        if not username_in_block or username_in_block.lower() != args.username.lower():
            profile_start2 = html.find('"profile":{"__typename":"User"', profile_start + 1)
            if profile_start2 != -1:
                block = html[profile_start2 : profile_start2 + 2000]
                username_in_block = _field(block, "username")

        if not username_in_block:
            raise RuntimeError("User not found.")

        result = {
            "site": "Product Hunt",
            "username": username_in_block,
            "name": _field(block, "name"),
            "headline": _field(block, "headline"),
            "twitter": _field(block, "twitterUsername"),
            "website": _field(block, "websiteUrl"),
            "followers": int(_field(block, "followersCount")) if _field(block, "followersCount") else None,
            "following": int(_field(block, "followingsCount")) if _field(block, "followingsCount") else None,
            "products": int(_field(block, "productsCount")) if _field(block, "productsCount") else None,
            "posts_submitted": int(_field(block, "submittedPostsCount")) if _field(block, "submittedPostsCount") else None,
            "collections": int(_field(block, "collectionsCount")) if _field(block, "collectionsCount") else None,
            "reviews": int(_field(block, "reviewsCount")) if _field(block, "reviewsCount") else None,
            "is_maker": _field(block, "isMaker") == "true" if _field(block, "isMaker") else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
