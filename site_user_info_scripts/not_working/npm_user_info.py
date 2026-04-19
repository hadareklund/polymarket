#!/usr/bin/env python3
"""Fetch user profile information from npm."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get npm user info by username.")
    parser.add_argument("username", help="npm username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://registry.npmjs.org/-/user/org.couchdb.user:{args.username}", timeout=args.timeout)
        if "error" in data: raise RuntimeError(data["error"])
        result = {
            "site": "npm",
            "username": data.get("name"),
            "email": data.get("email"),
            "profile_url": f"https://www.npmjs.com/~{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
