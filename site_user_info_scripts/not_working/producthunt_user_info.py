#!/usr/bin/env python3
"""Fetch user profile information from Product Hunt (GraphQL)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Product Hunt user info by username.")
    parser.add_argument("username", help="Product Hunt username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        import json as _json
        from urllib.request import Request, urlopen
        query = """
query ($username: String!) {
  user(username: $username) {
    name username headline websiteUrl twitterUsername
    followersCount followingCount votesCount
    profileImage
  }
}"""
        payload = _json.dumps({"query": query, "variables": {"username": args.username}}).encode()
        req = Request("https://api.producthunt.com/v2/api/graphql", data=payload, headers={"Content-Type": "application/json", "User-Agent": "site-user-info-scripts/1.0"})
        with urlopen(req, timeout=args.timeout) as r:
            data = _json.loads(r.read().decode())
        u = (data.get("data") or {}).get("user") or {}
        if not u: raise RuntimeError("User not found.")
        result = {
            "site": "Product Hunt",
            "username": u.get("username"),
            "name": u.get("name"),
            "headline": u.get("headline"),
            "website": u.get("websiteUrl"),
            "twitter": u.get("twitterUsername"),
            "followers": u.get("followersCount"),
            "following": u.get("followingCount"),
            "votes": u.get("votesCount"),
            "profile_url": f"https://www.producthunt.com/@{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
