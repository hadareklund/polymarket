#!/usr/bin/env python3
"""Telegram — not scrapeable: Telegram has no public profile lookup by username without the Telegram Bot API (requires bot token and the user to have messaged your bot)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Telegram user info by username.")
    parser.add_argument("username", help="Telegram username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "Telegram cannot be scraped automatically: Telegram has no public profile lookup by username without the Telegram Bot API (requires bot token and the user to have messaged your bot)."
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
