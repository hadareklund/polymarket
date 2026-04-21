#!/usr/bin/env python3
"""Fetch user profile information from note.com via its public REST API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get note.com user info by username.")
    parser.add_argument("username", help="note.com username (urlname)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://note.com/api/v2/creators/{args.username}",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=args.timeout,
        )
        if data.get("error") or not data.get("data"):
            raise RuntimeError(data.get("error") or "User not found.")
        d = data["data"]
        result = {
            "site": "note.com",
            "username": d.get("urlname"),
            "display_name": d.get("nickname"),
            "bio": d.get("profile"),
            "note_count": d.get("noteCount"),
            "follower_count": d.get("followerCount"),
            "following_count": d.get("followingCount"),
            "avatar_url": d.get("profileImageUrl"),
            "profile_url": f"https://note.com/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
