#!/usr/bin/env python3
"""Fetch user profile information from Duolingo."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Duolingo user info by username.")
    parser.add_argument("username", help="Duolingo username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://www.duolingo.com/2017-06-30/users?username={args.username}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=args.timeout,
        )
        users = data.get("users") or []
        if not users:
            raise RuntimeError("User not found.")
        u = users[0]
        result = {
            "site": "Duolingo",
            "username": u.get("username"),
            "display_name": u.get("name") or None,
            "bio": u.get("bio") or None,
            "location": u.get("location") or None,
            "total_xp": u.get("totalXp"),
            "streak": u.get("streak"),
            "courses": [c.get("title") for c in (u.get("courses") or []) if c.get("title")],
            "profile_url": f"https://www.duolingo.com/profile/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
