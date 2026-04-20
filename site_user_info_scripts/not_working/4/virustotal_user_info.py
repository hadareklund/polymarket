#!/usr/bin/env python3
"""Fetch user profile information from VirusTotal (requires VIRUSTOTAL_API_KEY)."""

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
    parser = argparse.ArgumentParser(description="Get VirusTotal user info.")
    parser.add_argument("username", help="VirusTotal username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    key = os.environ.get("VIRUSTOTAL_API_KEY", "")
    if not key:
        print("Error: VIRUSTOTAL_API_KEY not set. Get one at https://www.virustotal.com/gui/join-us", file=sys.stderr)
        return 1
    try:
        data = fetch_json(f"https://www.virustotal.com/api/v3/users/{args.username}", headers={"x-apikey": key}, timeout=args.timeout)
        attrs = (data.get("data") or {}).get("attributes") or {}
        result = {
            "site": "VirusTotal",
            "username": attrs.get("name"),
            "email": attrs.get("email"),
            "status": attrs.get("status"),
            "profile_url": f"https://www.virustotal.com/gui/user/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
