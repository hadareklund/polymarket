#!/usr/bin/env python3
"""Fetch user profile information from Monkeytype."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Monkeytype user info by username.")
    parser.add_argument("username", help="Monkeytype username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.monkeytype.com/users/{args.username}/profile", timeout=args.timeout)
        if data.get("message") and "not found" in data.get("message","").lower():
            raise RuntimeError("User not found.")
        d = (data.get("data") or {})
        result = {
            "site": "Monkeytype",
            "username": d.get("name"),
            "bio": d.get("bio"),
            "keyboard": d.get("keyboard"),
            "twitter": d.get("twitter"),
            "github": d.get("github"),
            "discord": d.get("discord"),
            "profile_url": f"https://monkeytype.com/profile/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
