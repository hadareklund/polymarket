#!/usr/bin/env python3
"""Fetch user profile information from Genius (requires GENIUS_API_KEY)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, load_env_file

load_env_file()


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Genius user info by username.")
    parser.add_argument("username", help="Genius username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("GENIUS_API_KEY", "")
    if not key:
        print("Error: GENIUS_API_KEY not set. Get one at https://genius.com/api-clients", file=sys.stderr)
        return 1
    try:
        search = fetch_json(f"https://api.genius.com/search?q={quote(args.username)}", headers={"Authorization": f"Bearer {key}"}, timeout=args.timeout)
        # Search for user by name in users endpoint
        data = fetch_json(f"https://api.genius.com/users/{quote(args.username)}", headers={"Authorization": f"Bearer {key}"}, timeout=args.timeout)
        u = (data.get("response") or {}).get("user") or {}
        result = {
            "site": "Genius",
            "username": u.get("login"),
            "name": u.get("name"),
            "bio": (u.get("about_me") or {}).get("plain"),
            "followers": u.get("followers_count"),
            "iq": u.get("iq"),
            "profile_url": u.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
