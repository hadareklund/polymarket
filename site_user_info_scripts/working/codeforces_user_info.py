#!/usr/bin/env python3
"""Fetch user profile information from Codeforces (public REST API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, unix_to_iso


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Codeforces user info by handle.")
    parser.add_argument("username", help="Codeforces handle")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://codeforces.com/api/user.info?handles={args.username}",
            timeout=args.timeout,
        )
        if data.get("status") != "OK":
            raise RuntimeError(data.get("comment", "Not found."))
        u = (data.get("result") or [{}])[0]
        result = {
            "site": "Codeforces",
            "username": u.get("handle"),
            "first_name": u.get("firstName"),
            "last_name": u.get("lastName"),
            "rank": u.get("rank"),
            "max_rank": u.get("maxRank"),
            "rating": u.get("rating"),
            "max_rating": u.get("maxRating"),
            "country": u.get("country"),
            "city": u.get("city"),
            "organization": u.get("organization"),
            "contribution": u.get("contribution"),
            "friend_of_count": u.get("friendOfCount"),
            "registered_at": unix_to_iso(u["registrationTimeSeconds"]) if u.get("registrationTimeSeconds") else None,
            "last_online_at": unix_to_iso(u["lastOnlineTimeSeconds"]) if u.get("lastOnlineTimeSeconds") else None,
            "avatar_url": u.get("avatar"),
            "title_photo_url": u.get("titlePhoto"),
            "profile_url": f"https://codeforces.com/profile/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
