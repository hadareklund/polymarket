#!/usr/bin/env python3
"""Fetch user profile information from RuneScape."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get RuneScape user info by username.")
    parser.add_argument("username", help="RuneScape username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://apps.runescape.com/runemetrics/profile/profile?user={args.username}&activities=0", timeout=args.timeout)
        if data.get("error"): raise RuntimeError(data["error"])
        result = {
            "site": "RuneScape",
            "username": data.get("name"),
            "rank": data.get("rank"),
            "total_xp": data.get("totalxp"),
            "total_level": data.get("totalskill"),
            "combat_level": data.get("combatlevel"),
            "quests_complete": data.get("questscomplete"),
            "profile_url": f"https://apps.runescape.com/runemetrics/app/overview/player/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
