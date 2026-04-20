#!/usr/bin/env python3
"""Fetch user profile information from TETR.IO."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get TETR.IO user info by username.")
    parser.add_argument("username", help="TETR.IO username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://ch.tetr.io/api/users/{args.username}", timeout=args.timeout)
        if not data.get("success"): raise RuntimeError(data.get("error", {}).get("msg", "Not found."))
        u = data.get("data") or {}
        result = {
            "site": "TETR.IO",
            "username": u.get("username"),
            "xp": u.get("xp"),
            "country": u.get("country"),
            "supporter": u.get("supporter"),
            "verified": u.get("verified"),
            "profile_url": f"https://tetr.io/u/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
