#!/usr/bin/env python3
"""Fetch user profile information from Imgur (requires IMGUR_CLIENT_ID)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, load_env_file

load_env_file()


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Imgur user info by username.")
    parser.add_argument("username", help="Imgur username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    client_id = os.environ.get("IMGUR_CLIENT_ID", "")
    if not client_id:
        print("Error: IMGUR_CLIENT_ID not set. Get one at https://api.imgur.com/oauth2/addclient", file=sys.stderr)
        return 1
    try:
        data = fetch_json(f"https://api.imgur.com/3/account/{args.username}", headers={"Authorization": f"Client-ID {client_id}"}, timeout=args.timeout)
        if not data.get("success"): raise RuntimeError(data.get("data", {}).get("error", "Not found."))
        u = data.get("data") or {}
        result = {
            "site": "Imgur",
            "username": u.get("url"),
            "bio": u.get("bio"),
            "reputation": u.get("reputation"),
            "created_at": u.get("created"),
            "profile_url": f"https://imgur.com/user/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
