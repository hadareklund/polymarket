#!/usr/bin/env python3
"""Fetch user profile information from LeetCode (GraphQL)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get LeetCode user info by username.")
    parser.add_argument("username", help="LeetCode username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        import json as _json
        from urllib.request import Request, urlopen
        query = """
query ($username: String!) {
  matchedUser(username: $username) {
    username
    profile { realName countryName company school ranking }
    submitStats { acSubmissionNum { difficulty count } }
  }
}"""
        payload = _json.dumps({"query": query, "variables": {"username": args.username}}).encode()
        req = Request("https://leetcode.com/graphql", data=payload, headers={"Content-Type": "application/json", "User-Agent": "site-user-info-scripts/1.0"})
        with urlopen(req, timeout=args.timeout) as r:
            data = _json.loads(r.read().decode())
        u = (data.get("data") or {}).get("matchedUser") or {}
        if not u: raise RuntimeError("User not found.")
        prof = u.get("profile") or {}
        result = {
            "site": "LeetCode",
            "username": u.get("username"),
            "name": prof.get("realName"),
            "country": prof.get("countryName"),
            "company": prof.get("company"),
            "school": prof.get("school"),
            "ranking": prof.get("ranking"),
            "solved": sum(s.get("count", 0) for s in (u.get("submitStats") or {}).get("acSubmissionNum", [])),
            "profile_url": f"https://leetcode.com/{args.username}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
