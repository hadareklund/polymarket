#!/usr/bin/env python3
"""Fetch user profile information from Lichess."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Lichess user info by username.")
    parser.add_argument("username", help="Lichess username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://lichess.org/api/user/{args.username}", timeout=args.timeout)
        if "error" in data: raise RuntimeError(data["error"])
        perf = data.get("perfs") or {}
        result = {
            "site": "Lichess",
            "username": data.get("username"),
            "title": data.get("title"),
            "bio": (data.get("profile") or {}).get("bio"),
            "country": (data.get("profile") or {}).get("country"),
            "location": (data.get("profile") or {}).get("location"),
            "real_name": (data.get("profile") or {}).get("realName"),
            "followers": data.get("nbFollowers"),
            "following": data.get("nbFollowing"),
            "games_played": (data.get("count") or {}).get("all"),
            "rating_bullet": (perf.get("bullet") or {}).get("rating"),
            "rating_blitz": (perf.get("blitz") or {}).get("rating"),
            "rating_rapid": (perf.get("rapid") or {}).get("rating"),
            "created_at": data.get("createdAt"),
            "profile_url": f"https://lichess.org/@/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
