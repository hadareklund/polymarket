#!/usr/bin/env python3
"""Fetch user profile information from GitLab (public REST API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get GitLab user info by username.")
    parser.add_argument("username", help="GitLab username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://gitlab.com/api/v4/users?username={args.username}",
            timeout=args.timeout,
        )
        users = data if isinstance(data, list) else []
        if not users:
            raise RuntimeError("User not found.")
        u = users[0]
        result = {
            "site": "GitLab",
            "username": u.get("username"),
            "name": u.get("name"),
            "state": u.get("state"),
            "avatar_url": u.get("avatar_url"),
            "profile_url": u.get("web_url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
