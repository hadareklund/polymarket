#!/usr/bin/env python3
"""Fetch user profile information from GitLab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get GitLab user info by username.")
    parser.add_argument("username", help="GitLab username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://gitlab.com/api/v4/users?username={args.username}", timeout=args.timeout)
        users = data if isinstance(data, list) else []
        if not users: raise RuntimeError("User not found.")
        u = users[0]
        result = {
            "site": "GitLab",
            "username": u.get("username"),
            "name": u.get("name"),
            "bio": u.get("bio"),
            "location": u.get("location"),
            "website": u.get("website_url"),
            "avatar_url": u.get("avatar_url"),
            "followers": u.get("followers"),
            "following": u.get("following"),
            "public_repos": u.get("public_repos"),
            "created_at": u.get("created_at"),
            "profile_url": u.get("web_url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
