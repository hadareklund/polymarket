#!/usr/bin/env python3
"""Fetch user profile information from Lemmy World."""

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
        data = fetch_json(f"https://lemmy.world/api/v3/user?username={args.username}", timeout=args.timeout)
        u = (data.get("person_view") or {}).get("person") or {}
        if not u: raise RuntimeError("User not found.")
        agg = (data.get("person_view") or {}).get("counts") or {}
        result = {
            "site": "Lemmy World",
            "username": u.get("name"),
            "display_name": u.get("display_name"),
            "bio": u.get("bio"),
            "post_count": agg.get("post_count"),
            "comment_count": agg.get("comment_count"),
            "profile_url": u.get("actor_id"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
