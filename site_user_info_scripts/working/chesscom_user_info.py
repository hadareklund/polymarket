#!/usr/bin/env python3
"""Fetch user profile information from chess.com public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, unix_to_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get chess.com user info by username.")
    parser.add_argument("username", help="chess.com username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _country_from_url(country_url: str | None) -> str | None:
    if not country_url or "/" not in country_url:
        return None
    return country_url.rstrip("/").split("/")[-1]


def main() -> int:
    args = parse_args()
    endpoint = f"https://api.chess.com/pub/player/{quote(args.username)}"
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        result = {
            "site": "chess.com",
            "username": data.get("username"),
            "name": data.get("name"),
            "location": data.get("location"),
            "country_code": _country_from_url(data.get("country")),
            "country_url": data.get("country"),
            "status": data.get("status"),
            "joined_unix": data.get("joined"),
            "joined_at": unix_to_iso(data.get("joined")),
            "last_online_unix": data.get("last_online"),
            "last_online_at": unix_to_iso(data.get("last_online")),
            "twitch_url": data.get("twitch_url"),
            "profile_url": data.get("url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
