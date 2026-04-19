#!/usr/bin/env python3
"""Fetch user profile information from BitBucket."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get BitBucket user info by username.")
    parser.add_argument("username", help="BitBucket username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://api.bitbucket.org/2.0/users/{args.username}", timeout=args.timeout)
        if "error" in data: raise RuntimeError(str(data["error"]))
        result = {
            "site": "BitBucket",
            "username": data.get("nickname"),
            "display_name": data.get("display_name"),
            "bio": data.get("description"),
            "location": data.get("location"),
            "website": data.get("website"),
            "account_status": data.get("account_status"),
            "created_on": data.get("created_on"),
            "profile_url": (data.get("links") or {}).get("html", {}).get("href"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
