#!/usr/bin/env python3
"""Gravatar — not scrapeable: Gravatar profiles are keyed by email MD5 hash, not username. Without the email address, username lookup is not possible."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Gravatar user info by username.")
    parser.add_argument("username", help="Gravatar username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "Gravatar cannot be scraped automatically: Gravatar profiles are keyed by email MD5 hash, not username. Without the email address, username lookup is not possible."
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
