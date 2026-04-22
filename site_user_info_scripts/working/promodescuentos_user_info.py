#!/usr/bin/env python3
"""Fetch user profile information from Promodescuentos (window.__INITIAL_STATE__ scraper)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json, unix_to_iso


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Promodescuentos user info by username.")
    parser.add_argument("username", help="Promodescuentos username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.promodescuentos.com/profile/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        state_m = re.search(
            r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;(?=\s*(?:window|</script))",
            html,
            re.DOTALL,
        )
        if not state_m:
            raise RuntimeError("Could not find __INITIAL_STATE__ in page.")

        raw_state = state_m.group(1)
        user_m = re.search(
            r'"user"\s*:\s*(\{[^{}]*(?:\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}[^{}]*)*\})',
            raw_state,
        )
        if not user_m:
            raise RuntimeError("Could not find user block in __INITIAL_STATE__.")

        u = json.loads(user_m.group(1))

        stats = u.get("userStats") or {}
        badges = [
            b.get("level", {}).get("name")
            for b in (u.get("badges") or [])
            if b.get("level", {}).get("name")
        ]

        result = {
            "site": "Promodescuentos",
            "username": u.get("username"),
            "user_id": u.get("userId"),
            "title": u.get("title") or None,
            "is_merchant": u.get("isMerchant"),
            "joined_ago": u.get("joinedAgo"),
            "created_at": unix_to_iso(u.get("createdAt")),
            "active_deals": stats.get("activeDealsCount"),
            "likes": stats.get("likeCount"),
            "comments": stats.get("commentCount"),
            "badges": badges or None,
            "loyalty_tier": u.get("loyaltyTier"),
            "avatar_url": u.get("avatar"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
