#!/usr/bin/env python3
"""Fetch user profile information from Speedrun.com."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Speedrun.com user info by username.")
    parser.add_argument("username", help="Speedrun.com username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://www.speedrun.com/api/v1/users/{args.username}", timeout=args.timeout)
        u = data.get("data") or {}
        if not u:
            raise RuntimeError("User not found.")
        names = u.get("names") or {}
        links = {ln["rel"]: ln["uri"] for ln in (u.get("links") or []) if ln.get("rel") and ln.get("uri")}
        result = {
            "site": "Speedrun.com",
            "username": names.get("international"),
            "location": ((u.get("location") or {}).get("country") or {}).get("names", {}).get("international"),
            "role": u.get("role"),
            "signup": u.get("signup"),
            "twitch": (u.get("twitch") or {}).get("uri"),
            "youtube": (u.get("youtube") or {}).get("uri"),
            "twitter": (u.get("twitter") or {}).get("uri"),
            "speedrunslive": (u.get("speedrunslive") or {}).get("uri"),
            "profile_url": u.get("weblink") or f"https://www.speedrun.com/user/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
