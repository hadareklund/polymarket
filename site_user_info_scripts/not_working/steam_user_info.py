#!/usr/bin/env python3
"""Fetch user profile information from Steam (requires STEAM_API_KEY)."""

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


def _resolve_vanity(vanity: str, key: str, timeout: int) -> str:
    data = fetch_json(f"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?vanityurl={vanity}&key={key}", timeout=timeout)
    r = data.get("response") or {}
    if r.get("success") != 1: raise RuntimeError("Vanity URL not found.")
    return r["steamid"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Steam user info by vanity URL.")
    parser.add_argument("username", help="Steam vanity URL (custom URL)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("STEAM_API_KEY", "")
    if not key:
        print("Error: STEAM_API_KEY not set. Get one at https://steamcommunity.com/dev/apikey", file=sys.stderr)
        return 1
    try:
        steam_id = _resolve_vanity(args.username, key, args.timeout)
        data = fetch_json(f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?steamids={steam_id}&key={key}", timeout=args.timeout)
        players = (data.get("response") or {}).get("players") or []
        if not players: raise RuntimeError("User not found.")
        p = players[0]
        result = {
            "site": "Steam",
            "steam_id": p.get("steamid"),
            "username": p.get("personaname"),
            "real_name": p.get("realname"),
            "country": p.get("loccountrycode"),
            "avatar_url": p.get("avatarfull"),
            "created": p.get("timecreated"),
            "profile_url": p.get("profileurl"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
