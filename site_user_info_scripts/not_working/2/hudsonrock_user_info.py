#!/usr/bin/env python3
"""Fetch user profile information from HudsonRock."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get HudsonRock user info by username.")
    parser.add_argument("username", help="HudsonRock username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/is-user-compromised?username={args.username}", timeout=args.timeout)
        result = {
            "site": "HudsonRock",
            "username": args.username,
            "compromised": data.get("have_it"),
            "stealers": data.get("stealers"),
            "total_credentials": data.get("total_credentials"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
