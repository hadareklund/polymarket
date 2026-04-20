#!/usr/bin/env python3
"""Fetch user profile information from MyAnimeList via the Jikan public REST API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get MyAnimeList user info by username.")
    parser.add_argument("username", help="MyAnimeList username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.jikan.moe/v4/users/{args.username}", timeout=args.timeout)
        if "error" in data:
            raise RuntimeError(data.get("error", "Not found."))
        d = data.get("data") or {}
        result = {
            "site": "MyAnimeList",
            "username": d.get("username"),
            "gender": d.get("gender"),
            "location": d.get("location"),
            "birthday": d.get("birthday"),
            "joined": d.get("joined"),
            "last_online": d.get("last_online"),
            "avatar_url": (d.get("images") or {}).get("jpg", {}).get("image_url"),
            "profile_url": d.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
