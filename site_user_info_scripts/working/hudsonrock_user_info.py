#!/usr/bin/env python3
"""Fetch breach/infostealer exposure data from HudsonRock Cavalier API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get HudsonRock infostealer data by username.")
    parser.add_argument("username", help="Username to search")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username?username={args.username}"
        data = fetch_json(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)

        stealers = data.get("stealers") or []
        result = {
            "site": "HudsonRock",
            "username": args.username,
            "compromised": len(stealers) > 0,
            "stealer_count": len(stealers),
            "total_corporate_services": data.get("total_corporate_services"),
            "total_user_services": data.get("total_user_services"),
            "stealers": [
                {
                    "date_compromised": s.get("date_compromised"),
                    "stealer_family": s.get("stealer_family"),
                    "computer_name": s.get("computer_name"),
                    "operating_system": s.get("operating_system"),
                    "total_user_services": s.get("total_user_services"),
                    "total_corporate_services": s.get("total_corporate_services"),
                    "ip": s.get("ip"),
                    "antiviruses": s.get("antiviruses"),
                }
                for s in stealers
            ],
            "profile_url": f"https://cavalier.hudsonrock.com/",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
