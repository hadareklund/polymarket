#!/usr/bin/env python3
"""Fetch user profile information from Bitbucket.

Bitbucket's public API supports workspace slugs (team/org accounts) and
personal user accounts via the /2.0/users/{account_id} endpoint. Username-based
lookup falls back to the workspace API when the user account endpoint 404s,
since many individual accounts are surfaced as workspaces on Bitbucket Cloud.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def _workspace_data(slug: str, timeout: int) -> dict:
    data = fetch_json(f"https://api.bitbucket.org/2.0/workspaces/{slug}", timeout=timeout)
    links = data.get("links", {})
    return {
        "account_type": "workspace",
        "display_name": data.get("name"),
        "slug": data.get("slug"),
        "uuid": data.get("uuid"),
        "is_private": data.get("is_private"),
        "created_on": data.get("created_on"),
        "avatar_url": links.get("avatar", {}).get("href"),
        "profile_url": links.get("html", {}).get("href"),
    }


def _user_data(username: str, timeout: int) -> dict:
    data = fetch_json(f"https://api.bitbucket.org/2.0/users/{username}", timeout=timeout)
    if "error" in data:
        raise RuntimeError(str(data["error"]))
    links = data.get("links", {})
    return {
        "account_type": "user",
        "display_name": data.get("display_name"),
        "nickname": data.get("nickname"),
        "bio": data.get("description"),
        "location": data.get("location"),
        "website": data.get("website"),
        "account_status": data.get("account_status"),
        "created_on": data.get("created_on"),
        "avatar_url": links.get("avatar", {}).get("href"),
        "profile_url": links.get("html", {}).get("href"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Bitbucket user/workspace info by slug.")
    parser.add_argument("username", help="Bitbucket username or workspace slug")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        try:
            account = _workspace_data(args.username, args.timeout)
        except Exception:
            account = _user_data(args.username, args.timeout)

        result = {"site": "Bitbucket", "username": args.username, **account}
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
