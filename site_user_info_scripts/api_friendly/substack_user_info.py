#!/usr/bin/env python3
"""Fetch user profile information from Substack public profile endpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Substack user info by handle.")
    parser.add_argument("username", help="Substack handle")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoint = f"https://substack.com/api/v1/user/{quote(args.username)}/public_profile"

    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        publication_users = data.get("publicationUsers")
        if publication_users is None:
            publication_users = data.get("publication_users")

        result = {
            "site": "Substack",
            "endpoint": endpoint,
            "lookup": args.username,
            "id": data.get("id"),
            "handle": data.get("handle") or args.username,
            "name": data.get("name"),
            "bio": data.get("bio"),
            "photo_url": data.get("photo_url"),
            "profile_set_up_at": data.get("profile_set_up_at"),
            "publication_users": publication_users or [],
            "profile_url": f"https://substack.com/@{quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
