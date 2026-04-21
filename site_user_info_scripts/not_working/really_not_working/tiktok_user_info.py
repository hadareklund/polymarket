#!/usr/bin/env python3
"""TikTok — not scrapeable: TikTok aggressively blocks automated requests. Requires Playwright with a valid session cookie (TIKTOK_SESSION_ID) or the unofficial mobile API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get TikTok user info by username.")
    parser.add_argument("username", help="TikTok username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "TikTok cannot be scraped automatically: TikTok aggressively blocks automated requests. Requires Playwright with a valid session cookie (TIKTOK_SESSION_ID) or the unofficial mobile API."
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
