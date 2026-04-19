#!/usr/bin/env python3
"""Fetch user profile information from Launchpad."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Launchpad user info by username.")
    parser.add_argument("username", help="Launchpad username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.launchpad.net/1.0/~{args.username}", timeout=args.timeout)
        if "message" in data: raise RuntimeError(data["message"])
        result = {
            "site": "Launchpad",
            "username": data.get("name"),
            "display_name": data.get("display_name"),
            "bio": data.get("description"),
            "location": data.get("location"),
            "time_zone": data.get("time_zone"),
            "karma": data.get("karma"),
            "profile_url": data.get("web_link"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
