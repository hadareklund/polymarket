#!/usr/bin/env python3
"""Fetch user profile information from Hive Blog (blockchain social network)."""

from __future__ import annotations

import argparse
import json as _json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Hive Blog user info by username.")
    parser.add_argument("username", help="Hive Blog username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        payload = _json.dumps({
            "jsonrpc": "2.0",
            "method": "condenser_api.get_accounts",
            "params": [[args.username]],
            "id": 1,
        }).encode()
        req = Request(
            "https://api.hive.blog",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "site-user-info-scripts/1.0"},
        )
        with urlopen(req, timeout=args.timeout) as r:
            data = _json.loads(r.read().decode())
        accounts = data.get("result") or []
        if not accounts:
            raise RuntimeError("User not found.")
        u = accounts[0]
        meta = _json.loads(u.get("json_metadata") or "{}").get("profile", {})
        if not meta:
            meta = _json.loads(u.get("posting_json_metadata") or "{}").get("profile", {})
        result = {
            "site": "Hive Blog",
            "username": u.get("name"),
            "display_name": meta.get("name"),
            "bio": meta.get("about"),
            "location": meta.get("location"),
            "website": meta.get("website"),
            "avatar_url": meta.get("profile_image"),
            "post_count": u.get("post_count"),
            "created": u.get("created"),
            "profile_url": f"https://peakd.com/@{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
