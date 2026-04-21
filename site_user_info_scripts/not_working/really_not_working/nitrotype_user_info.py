#!/usr/bin/env python3
"""Fetch user profile information from NitroType."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get NitroType user info by username.")
    parser.add_argument("username", help="NitroType username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://www.nitrotype.com/api/v2/racers/{args.username}", timeout=args.timeout)
        u = (data.get("data") or {}).get("racer") or {}
        if not u: raise RuntimeError("User not found.")
        result = {
            "site": "NitroType",
            "username": u.get("username"),
            "display_name": u.get("displayName"),
            "tag": u.get("tag"),
            "avg_speed": u.get("avgSpeed"),
            "races_played": u.get("racesPlayed"),
            "profile_url": f"https://www.nitrotype.com/racer/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
