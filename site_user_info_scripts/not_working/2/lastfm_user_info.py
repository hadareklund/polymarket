#!/usr/bin/env python3
"""Fetch user profile information from Last.fm (requires LASTFM_API_KEY)."""

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
    parser = argparse.ArgumentParser(description="Get Last.fm user info by username.")
    parser.add_argument("username", help="Last.fm username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("LASTFM_API_KEY", "")
    if not key:
        print("Error: LASTFM_API_KEY not set. Get one at https://www.last.fm/api/account/create", file=sys.stderr)
        return 1
    try:
        url = f"https://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={quote(args.username)}&api_key={key}&format=json"
        data = fetch_json(url, timeout=args.timeout)
        if "error" in data:
            raise RuntimeError(data.get("message", "Not found."))
        u = data.get("user") or {}
        result = {
            "site": "Last.fm",
            "username": u.get("name"),
            "real_name": u.get("realname"),
            "country": u.get("country"),
            "scrobbles": u.get("playcount"),
            "registered": (u.get("registered") or {}).get("#text"),
            "profile_url": u.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
