#!/usr/bin/env python3
"""Fetch user profile information from Twitch (requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json as _json

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, load_env_file

load_env_file()


def _get_token(client_id: str, client_secret: str) -> str:
    payload = urlencode({"client_id": client_id, "client_secret": client_secret, "grant_type": "client_credentials"}).encode()
    req = Request("https://id.twitch.tv/oauth2/token", data=payload)
    with urlopen(req, timeout=15) as r:
        return _json.loads(r.read())["access_token"]


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Twitch user info by username.")
    parser.add_argument("username", help="Twitch login name")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    client_id = os.environ.get("TWITCH_CLIENT_ID", "")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "")
    if not client_id or not client_secret:
        print("Error: Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET. Register at https://dev.twitch.tv/console", file=sys.stderr)
        return 1
    try:
        token = _get_token(client_id, client_secret)
        data = fetch_json(f"https://api.twitch.tv/helix/users?login={args.username}", headers={"Client-Id": client_id, "Authorization": f"Bearer {token}"}, timeout=args.timeout)
        users = data.get("data") or []
        if not users: raise RuntimeError("User not found.")
        u = users[0]
        result = {
            "site": "Twitch",
            "username": u.get("login"),
            "display_name": u.get("display_name"),
            "bio": u.get("description"),
            "view_count": u.get("view_count"),
            "account_type": u.get("broadcaster_type"),
            "created_at": u.get("created_at"),
            "profile_image_url": u.get("profile_image_url"),
            "profile_url": f"https://www.twitch.tv/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
