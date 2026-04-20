#!/usr/bin/env python3
"""Fetch user profile information from Sketchfab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Sketchfab user info by username.")
    parser.add_argument("username", help="Sketchfab username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.sketchfab.com/v3/users/{args.username}", timeout=args.timeout)
        if "detail" in data: raise RuntimeError(data["detail"])
        result = {
            "site": "Sketchfab",
            "username": data.get("username"),
            "display_name": data.get("displayName"),
            "bio": data.get("biography"),
            "website": data.get("website"),
            "followers": data.get("followerCount"),
            "following": data.get("followingCount"),
            "model_count": data.get("modelCount"),
            "profile_url": (data.get("profileUrl") or f"https://sketchfab.com/{args.username}"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
