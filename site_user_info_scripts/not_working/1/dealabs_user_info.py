#!/usr/bin/env python3
"""Fetch user profile information from Dealabs (French deals site)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json, unix_to_iso


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
    parser = argparse.ArgumentParser(description="Get Dealabs user info by username.")
    parser.add_argument("username", help="Dealabs username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.dealabs.com/profile/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _meta(html, "og:title", attr="property")
        if not og_title or "404" in og_title:
            raise RuntimeError(f"User '{args.username}' not found on Dealabs.")

        og_image = _meta(html, "og:image", attr="property")
        og_desc = _meta(html, "og:description", attr="property")

        # Extract embedded __INITIAL_STATE__ JSON
        state_m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.+?\});\s*(?:</script>|window\.)", html, re.S)
        user_data: dict = {}
        if state_m:
            try:
                state = json.loads(state_m.group(1))
                user_data = state.get("user", {})
            except (json.JSONDecodeError, KeyError):
                pass

        badges = [
            b.get("level", {}).get("name")
            for b in user_data.get("badges", [])
            if b.get("level", {}).get("name")
        ]
        stats = user_data.get("userStats", {})

        result = {
            "site": "Dealabs",
            "username": user_data.get("username") or args.username,
            "quote": (user_data.get("settings") or {}).get("quote") or None,
            "joined_at": unix_to_iso(user_data.get("createdAt")),
            "is_online": user_data.get("isOnline"),
            "badges": badges or None,
            "active_deals": stats.get("activeDealsCount"),
            "comments": stats.get("commentCount"),
            "avatar_url": og_image,
            "description": og_desc or None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
