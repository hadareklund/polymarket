#!/usr/bin/env python3
"""Fetch user profile information from Pokemon Showdown (public JSON API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, unix_to_iso


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Pokemon Showdown user info by username.")
    parser.add_argument("username", help="Pokemon Showdown username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://pokemonshowdown.com/users/{args.username}.json",
            timeout=args.timeout,
        )
        if not data.get("userid"):
            raise RuntimeError("User not found.")

        ratings = data.get("ratings") or {}
        ladder: list[dict] = []
        for format_id, r in ratings.items():
            if r.get("elo") is not None:
                ladder.append({
                    "format": format_id,
                    "elo": round(r["elo"], 1),
                    "gxe": r.get("gxe"),
                    "wins": r.get("w"),
                    "losses": r.get("l"),
                })
        ladder.sort(key=lambda x: x["elo"], reverse=True)

        result = {
            "site": "Pokemon Showdown",
            "username": data.get("username"),
            "userid": data.get("userid"),
            "avatar": data.get("avatar"),
            "registered_at": unix_to_iso(data.get("registertime")),
            "group": data.get("group"),
            "ladder": ladder[:10],
            "profile_url": f"https://pokemonshowdown.com/users/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
