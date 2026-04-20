#!/usr/bin/env python3
"""Fetch user profile information from Trakt (requires TRAKT_CLIENT_ID)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, load_env_file

load_env_file()


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Trakt user info by username.")
    parser.add_argument("username", help="Trakt username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    client_id = os.environ.get("TRAKT_CLIENT_ID", "")
    if not client_id:
        print("Error: TRAKT_CLIENT_ID not set. Get one at https://trakt.tv/oauth/applications", file=sys.stderr)
        return 1
    try:
        data = fetch_json(f"https://api.trakt.tv/users/{args.username}", headers={"trakt-api-key": client_id, "trakt-api-version": "2"}, timeout=args.timeout)
        stats = fetch_json(f"https://api.trakt.tv/users/{args.username}/stats", headers={"trakt-api-key": client_id, "trakt-api-version": "2"}, timeout=args.timeout)
        result = {
            "site": "Trakt",
            "username": data.get("username"),
            "name": data.get("name"),
            "bio": data.get("about"),
            "location": data.get("location"),
            "movies_watched": (stats.get("movies") or {}).get("watched"),
            "shows_watched": (stats.get("shows") or {}).get("watched"),
            "profile_url": f"https://trakt.tv/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
