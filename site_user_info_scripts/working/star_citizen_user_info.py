#!/usr/bin/env python3
"""Fetch user profile information from Roberts Space Industries (Star Citizen)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _label_value(html: str, label: str) -> str | None:
    """Extract <strong class="value"> following a label span."""
    pattern = (
        rf'<span[^>]*class="label"[^>]*>\s*{re.escape(label)}\s*</span>'
        r'\s*<strong[^>]*class="value"[^>]*>(.*?)</strong>'
    )
    m = re.search(pattern, html, re.I | re.S)
    if not m:
        return None
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Star Citizen / RSI citizen info by handle.")
    parser.add_argument("username", help="RSI handle (case-sensitive)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://robertsspaceindustries.com/citizens/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        handle = _label_value(html, "Handle name")
        enlisted = _label_value(html, "Enlisted")
        location = _label_value(html, "Location")
        fluency = _label_value(html, "Fluency")
        citizen_record_m = re.search(r'UEE Citizen Record.*?<strong[^>]*class="value"[^>]*>#(\d+)', html, re.I | re.S)
        citizen_record = citizen_record_m.group(1) if citizen_record_m else None

        avatar_m = re.search(
            r'class="profile.*?<div[^>]*class="thumb"[^>]*>\s*<img[^>]+src="(/media/[^"]+)"',
            html, re.I | re.S,
        )
        avatar_url = f"https://robertsspaceindustries.com{avatar_m.group(1)}" if avatar_m else None

        result = {
            "site": "Star Citizen (RSI)",
            "username": handle or args.username,
            "citizen_record": citizen_record,
            "enlisted": enlisted,
            "location": location,
            "fluency": fluency,
            "avatar_url": avatar_url,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
