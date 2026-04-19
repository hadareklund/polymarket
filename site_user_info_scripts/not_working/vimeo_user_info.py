#!/usr/bin/env python3
"""Vimeo — not scrapeable: Vimeo requires a VIMEO_ACCESS_TOKEN from https://developer.vimeo.com/apps. The public API is limited without auth."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Vimeo user info by username.")
    parser.add_argument("username", help="Vimeo username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "Vimeo cannot be scraped automatically: Vimeo requires a VIMEO_ACCESS_TOKEN from https://developer.vimeo.com/apps. The public API is limited without auth."
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
