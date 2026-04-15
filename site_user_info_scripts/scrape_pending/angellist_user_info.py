#!/usr/bin/env python3
"""Placeholder collector for AngelList user info (scraping pending)."""

from __future__ import annotations

import argparse
import json

SITE_NAME = "AngelList"
NOTE = "No public API for this username lookup use case. Scraper flow is pending implementation."


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{SITE_NAME} user info collector (pending)")
    parser.add_argument("username", help="Username to investigate")
    args = parser.parse_args()

    payload = {
        "site": SITE_NAME,
        "username": args.username,
        "method": "scrape",
        "status": "pending",
        "note": NOTE,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
