#!/usr/bin/env python3
"""Fetch Steam Community group info (requires STEAM_API_KEY)."""

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
    parser = argparse.ArgumentParser(description="Get Steam Community group info.")
    parser.add_argument("username", help="Steam group name")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("STEAM_API_KEY", "")
    if not key:
        print("Error: STEAM_API_KEY not set.", file=sys.stderr)
        return 1
    try:
        data = fetch_json(f"https://api.steampowered.com/ISteamUser/GetGroupSummary/v1/?groupname={args.username}&key={key}", timeout=args.timeout)
        g = (data.get("response") or {}).get("group_details") or {}
        result = {
            "site": "Steam Community (Group)",
            "group_name": g.get("group_name"),
            "headline": g.get("headline"),
            "summary": g.get("summary"),
            "member_count": g.get("member_count"),
            "profile_url": f"https://steamcommunity.com/groups/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
