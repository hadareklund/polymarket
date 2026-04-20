#!/usr/bin/env python3
"""Fetch user profile information from omg.lol."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get omg.lol user info by username.")
    parser.add_argument("username", help="omg.lol username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.omg.lol/address/{args.username}/info", timeout=args.timeout)
        if data.get("request", {}).get("status_code") != 200:
            raise RuntimeError("Address not found.")
        info = (data.get("response") or {}).get("address") or {}
        result = {
            "site": "omg.lol",
            "username": info.get("address"),
            "message": info.get("message"),
            "profile_url": f"https://omg.lol/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
