#!/usr/bin/env python3
"""Fetch user profile information from Gitee."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Gitee user info by username.")
    parser.add_argument("username", help="Gitee username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://gitee.com/api/v5/users/{args.username}", timeout=args.timeout)
        if "message" in data: raise RuntimeError(data["message"])
        result = {
            "site": "Gitee",
            "username": data.get("login"),
            "name": data.get("name"),
            "bio": data.get("bio"),
            "blog": data.get("blog"),
            "public_repos": data.get("public_repos"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "created_at": data.get("created_at"),
            "profile_url": data.get("html_url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
