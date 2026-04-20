#!/usr/bin/env python3
"""Fetch user profile information from Scratch."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Scratch user info by username.")
    parser.add_argument("username", help="Scratch username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.scratch.mit.edu/users/{args.username}", timeout=args.timeout)
        if "id" not in data: raise RuntimeError("User not found.")
        result = {
            "site": "Scratch",
            "username": data.get("username"),
            "display_name": data.get("profile", {}).get("bio"),
            "bio": data.get("profile", {}).get("bio"),
            "country": data.get("profile", {}).get("country"),
            "joined": data.get("history", {}).get("joined"),
            "profile_url": f"https://scratch.mit.edu/users/{args.username}/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
