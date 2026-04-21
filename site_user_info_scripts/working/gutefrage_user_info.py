#!/usr/bin/env python3
"""Fetch user profile information from Gutefrage (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Gutefrage user info by username.")
    parser.add_argument("username", help="Gutefrage username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        url = f"https://www.gutefrage.net/nutzer/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        h1_m = re.search(r"<h1[^>]*>([^<]+)</h1>", html, re.I)
        # Answer count is embedded as element-count attribute on paginated sections
        counts = re.findall(r'element-count="(\d+)"', html)
        answer_count = int(counts[0]) if counts else None

        result = {
            "site": "Gutefrage",
            "username": args.username,
            "name": h1_m.group(1).strip() if h1_m else args.username,
            "answer_count": answer_count,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
