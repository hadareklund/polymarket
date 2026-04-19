#!/usr/bin/env python3
"""Fetch user profile information from AniList (GraphQL)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get AniList user info by username.")
    parser.add_argument("username", help="AniList username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        import json as _json
        from urllib.request import Request, urlopen
        query = """
query ($username: String) {
  User(name: $username) {
    name siteUrl
    about
    avatar { large }
    statistics { anime { count meanScore } manga { count } }
    followers { pageInfo { total } }
    following { pageInfo { total } }
  }
}"""
        payload = _json.dumps({"query": query, "variables": {"username": args.username}}).encode()
        req = Request("https://graphql.anilist.co", data=payload, headers={"Content-Type": "application/json", "User-Agent": "site-user-info-scripts/1.0"})
        with urlopen(req, timeout=args.timeout) as r:
            data = _json.loads(r.read().decode())
        u = (data.get("data") or {}).get("User") or {}
        if not u: raise RuntimeError("User not found.")
        result = {
            "site": "AniList",
            "username": u.get("name"),
            "bio": u.get("about"),
            "avatar_url": (u.get("avatar") or {}).get("large"),
            "anime_count": (u.get("statistics") or {}).get("anime", {}).get("count"),
            "anime_mean_score": (u.get("statistics") or {}).get("anime", {}).get("meanScore"),
            "manga_count": (u.get("statistics") or {}).get("manga", {}).get("count"),
            "profile_url": u.get("siteUrl"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
