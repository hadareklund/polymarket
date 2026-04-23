#!/usr/bin/env python3
"""Fetch user profile information from Docker Hub."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Docker Hub user info by username.")
    parser.add_argument("username", help="Docker Hub username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(
            f"https://hub.docker.com/v2/users/{args.username}/",
            timeout=args.timeout,
        )
        if data.get("detail") == "Not found.":
            raise RuntimeError("User not found.")
        result = {
            "site": "Docker Hub",
            "username": data.get("username"),
            "full_name": data.get("full_name") or None,
            "location": data.get("location") or None,
            "company": data.get("company") or None,
            "date_joined": data.get("date_joined"),
            "gravatar_url": data.get("gravatar_url") or None,
            "account_type": data.get("type"),
            "profile_url": f"https://hub.docker.com/u/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
