#!/usr/bin/env python3
"""Fetch user profile information from Snapchat (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _meta(html: str, name: str, attr: str = "name") -> str | None:
    for pattern in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Snapchat user info by username.")
    parser.add_argument("username", help="Snapchat username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.snapchat.com/add/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_image = _meta(html, "og:image", attr="property")

        # Prefer the embedded displayName JSON field over og:title (og:title is localised)
        dn_m = re.search(r'"displayName":"([^"]+)"', html)
        display_name = dn_m.group(1) if dn_m else _meta(html, "og:title", attr="property")

        snapcode_m = re.search(r'"snapcodeImageUrl":"([^"]+)"', html)
        snapcode_url = snapcode_m.group(1).replace("\\u0026", "&").replace("\\u002", "") if snapcode_m else None

        result = {
            "site": "Snapchat",
            "username": args.username,
            "display_name": display_name,
            "avatar_url": og_image,
            "snapcode_url": snapcode_url,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
