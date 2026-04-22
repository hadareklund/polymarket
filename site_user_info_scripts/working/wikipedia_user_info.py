#!/usr/bin/env python3
"""Fetch user profile information from Wikipedia's public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Wikipedia user info by username.")
    parser.add_argument("username", help="Wikipedia username")
    parser.add_argument("--lang", default="en", help="Wiki language code (default: en)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        base = f"https://{args.lang}.wikipedia.org/w/api.php"
        data = fetch_json(
            base,
            params={
                "action": "query",
                "list": "users",
                "ususers": args.username,
                "usprop": "editcount|registration|groups",
                "format": "json",
            },
            timeout=args.timeout,
        )
        users = data.get("query", {}).get("users", [])
        if not users:
            raise RuntimeError("No user data returned.")
        user = users[0]
        if "missing" in user or "invalid" in user:
            raise RuntimeError(f"User not found: {args.username}")

        groups = [g for g in user.get("groups", []) if g not in ("*", "user", "autoconfirmed")]
        result = {
            "site": "Wikipedia",
            "username": user.get("name"),
            "user_id": user.get("userid"),
            "edit_count": user.get("editcount"),
            "registered": user.get("registration"),
            "groups": groups or None,
            "profile_url": f"https://{args.lang}.wikipedia.org/wiki/User:{quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
