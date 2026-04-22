#!/usr/bin/env python3
"""Fetch WordPress.com blog/user info via the public REST API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get WordPress.com blog info by username.")
    parser.add_argument("username", help="WordPress.com username (subdomain)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    site_domain = f"{args.username}.wordpress.com"
    url = f"https://public-api.wordpress.com/rest/v1.1/sites/{site_domain}"
    try:
        data = fetch_json(url, timeout=args.timeout)
        icon = data.get("icon") or {}
        result = {
            "site": "WordPress.com",
            "username": args.username,
            "blog_title": data.get("name"),
            "description": data.get("description"),
            "blog_url": data.get("URL"),
            "subscribers_count": data.get("subscribers_count"),
            "avatar_url": icon.get("img"),
            "is_private": data.get("is_private"),
            "profile_url": f"https://{site_domain}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
