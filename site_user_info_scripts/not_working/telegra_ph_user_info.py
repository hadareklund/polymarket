#!/usr/bin/env python3
"""Fetch Telegra.ph page metadata by page path."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Get Telegra.ph page metadata by page path. Telegra.ph does not support username lookup."
        )
    )
    parser.add_argument("username", help="Page path (not a username)")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    path = args.username
    endpoint = f"https://api.telegra.ph/getPage/{quote(path)}"

    try:
        payload = fetch_json(
            endpoint,
            params={"return_content": "false"},
            timeout=args.timeout,
        )
        if not payload.get("ok"):
            raise RuntimeError(f"Telegra.ph API returned failure payload: {payload}")

        result_data = payload.get("result") or {}
        result = {
            "site": "Telegra.ph",
            "endpoint": endpoint,
            "lookup": path,
            "lookup_type": "page_path",
            "title": result_data.get("title"),
            "author_name": result_data.get("author_name"),
            "author_url": result_data.get("author_url"),
            "description": result_data.get("description"),
            "views": result_data.get("views"),
            "url": result_data.get("url") or f"https://telegra.ph/{quote(path)}",
            "note": "Telegra.ph has no username account API; this script resolves page metadata by page path.",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
