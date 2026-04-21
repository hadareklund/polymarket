#!/usr/bin/env python3
"""Fetch user profile information from Pepper.pl (window.__INITIAL_STATE__ JSON)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Pepper.pl user info by username.")
    parser.add_argument("username", help="Pepper.pl username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.pepper.pl/profile/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        m = re.search(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});\s*\n", html, re.S)
        if not m:
            raise RuntimeError("Could not find __INITIAL_STATE__ in page.")
        state = json.loads(m.group(1))

        user = state.get("user") or {}
        if user.get("isDeletedOrPendingDeletion"):
            raise RuntimeError("User is deleted.")

        stats = user.get("userStats") or {}
        badges = [b.get("level", {}).get("name") for b in (user.get("badges") or []) if b.get("level")]

        import datetime
        created_ts = user.get("createdAt")
        created_iso = (
            datetime.datetime.fromtimestamp(created_ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            if created_ts else None
        )

        result = {
            "site": "Pepper.pl",
            "username": user.get("username"),
            "title": user.get("title") or None,
            "quote": (user.get("settings") or {}).get("quote") or None,
            "is_merchant": user.get("isMerchant"),
            "active_deals": stats.get("activeDealsCount"),
            "likes": stats.get("likeCount"),
            "comments": stats.get("commentCount"),
            "badges": badges or None,
            "created_at": created_iso,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
