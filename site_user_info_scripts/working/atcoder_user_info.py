#!/usr/bin/env python3
"""Fetch user profile information from AtCoder."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, fetch_text, print_json


def _scrape_profile(username: str, timeout: int) -> dict:
    html = fetch_text(
        f"https://atcoder.jp/users/{username}",
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en"},
        timeout=timeout,
    )
    meta_pairs = re.findall(r"<th[^>]*>([^<]+)</th>\s*<td[^>]*>([^<]+)</td>", html)
    profile: dict = {}
    for k, v in meta_pairs:
        key = k.strip().lower()
        val = re.sub(r"<[^>]+>", "", v).strip()
        if "birth year" in key:
            profile["birth_year"] = val
        elif "affiliation" in key:
            profile["affiliation"] = val
        elif "rank" in key:
            profile["rank"] = val
        elif "last competed" in key:
            profile["last_competed"] = val

    # Colour-coded username span indicates rating tier
    tier_m = re.search(r'<span class="(user-\w+)">', html)
    if tier_m:
        profile["rating_tier"] = tier_m.group(1).replace("user-", "")

    return profile


def main() -> int:
    parser = argparse.ArgumentParser(description="Get AtCoder user info by username.")
    parser.add_argument("username", help="AtCoder username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        history = fetch_json(
            f"https://atcoder.jp/users/{args.username}/history/json",
            timeout=args.timeout,
        )
        contests = history if isinstance(history, list) else []
        profile = _scrape_profile(args.username, args.timeout)

        result = {
            "site": "AtCoder",
            "username": args.username,
            "rating": contests[-1]["NewRating"] if contests else None,
            "contests_participated": len(contests),
            "last_contest": contests[-1].get("ContestNameEn") or contests[-1].get("ContestName") if contests else None,
            "rank": profile.get("rank"),
            "rating_tier": profile.get("rating_tier"),
            "affiliation": profile.get("affiliation"),
            "birth_year": profile.get("birth_year"),
            "last_competed": profile.get("last_competed"),
            "profile_url": f"https://atcoder.jp/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
