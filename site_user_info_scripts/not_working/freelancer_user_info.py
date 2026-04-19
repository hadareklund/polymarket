#!/usr/bin/env python3
"""Freelancer — not scrapeable: Freelancer requires FREELANCER_OAUTH_TOKEN for its API. HTML profiles are JS-rendered."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Freelancer user info by username.")
    parser.add_argument("username", help="Freelancer username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "Freelancer cannot be scraped automatically: Freelancer requires FREELANCER_OAUTH_TOKEN for its API. HTML profiles are JS-rendered."
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
