#!/usr/bin/env python3
"""Disqus — not scrapeable: Disqus requires DISQUS_API_KEY and DISQUS_API_SECRET. Register at https://disqus.com/api/applications/"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Disqus user info by username.")
    parser.add_argument("username", help="Disqus username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        raise RuntimeError(
            "Disqus cannot be scraped automatically: Disqus requires DISQUS_API_KEY and DISQUS_API_SECRET. Register at https://disqus.com/api/applications/"
        )
        result = {}  # unreachable
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
