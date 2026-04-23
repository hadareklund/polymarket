#!/usr/bin/env python3
"""Fetch user profile information from Lemmy World (public REST API)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Lemmy World user info by username.")
    parser.add_argument("username", help="Lemmy World username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://lemmy.world/api/v3/user?username={args.username}",
            timeout=args.timeout,
        )
        if "error" in data:
            raise RuntimeError(data["error"])
        pv = data.get("person_view") or {}
        p = pv.get("person") or {}
        if not p:
            raise RuntimeError("User not found.")
        counts = pv.get("counts") or {}
        result = {
            "site": "Lemmy World",
            "username": p.get("name"),
            "display_name": p.get("display_name"),
            "bio": p.get("bio"),
            "avatar_url": p.get("avatar"),
            "banner_url": p.get("banner"),
            "published": p.get("published"),
            "bot_account": p.get("bot_account"),
            "post_count": counts.get("post_count"),
            "comment_count": counts.get("comment_count"),
            "profile_url": p.get("actor_id"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
