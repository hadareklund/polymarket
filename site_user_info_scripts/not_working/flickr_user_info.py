#!/usr/bin/env python3
"""Fetch user profile information from Flickr (requires FLICKR_API_KEY)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, load_env_file

load_env_file()


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Flickr user info by username.")
    parser.add_argument("username", help="Flickr username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("FLICKR_API_KEY", "")
    if not key:
        print("Error: FLICKR_API_KEY not set. Get one at https://www.flickr.com/services/api/keys/", file=sys.stderr)
        return 1
    try:
        base = "https://api.flickr.com/services/rest/?format=json&nojsoncallback=1"
        lookup = fetch_json(f"{base}&method=flickr.people.findByUsername&username={quote(args.username)}&api_key={key}", timeout=args.timeout)
        if lookup.get("stat") != "ok": raise RuntimeError(lookup.get("message", "Not found."))
        nsid = lookup["user"]["nsid"]
        info = fetch_json(f"{base}&method=flickr.people.getInfo&user_id={nsid}&api_key={key}", timeout=args.timeout)
        p = info.get("person") or {}
        result = {
            "site": "Flickr",
            "username": (p.get("username") or {}).get("_content"),
            "real_name": (p.get("realname") or {}).get("_content"),
            "location": (p.get("location") or {}).get("_content"),
            "photos": (p.get("photos") or {}).get("count", {}).get("_content"),
            "profile_url": (p.get("profileurl") or {}).get("_content"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
