#!/usr/bin/env python3
"""Fetch user profile information from Memrise."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Memrise user info by username.")
    parser.add_argument("username", help="Memrise username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://app.memrise.com/api/1/user/?username={args.username}", timeout=args.timeout)
        users = (data.get("users") or {}).get("results") or []
        if not users: raise RuntimeError("User not found.")
        u = users[0]
        result = {
            "site": "Memrise",
            "username": u.get("username"),
            "display_name": u.get("name"),
            "bio": u.get("tagline"),
            "points": u.get("points"),
            "courses": u.get("courses_count"),
            "profile_url": f"https://app.memrise.com/user/{args.username}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
