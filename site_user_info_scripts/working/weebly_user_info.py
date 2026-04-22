#!/usr/bin/env python3
"""Fetch site metadata from a Weebly-hosted site ({username}.weebly.com)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


def _meta(html: str, name: str, attr: str = "name") -> str | None:
    for pat in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Weebly site info by username.")
    parser.add_argument("username", help="Weebly username (subdomain)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://{args.username}.weebly.com"
        html = fetch_text(url, headers={"User-Agent": UA}, timeout=args.timeout)
        if len(html) < 200:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        site_title = (
            _meta(html, "og:title", "property")
            or (title_m.group(1).strip() if title_m else None)
        )
        description = _meta(html, "og:description", "property") or _meta(html, "description")
        avatar_url = _meta(html, "og:image", "property")

        result = {
            "site": "Weebly",
            "username": args.username,
            "site_title": site_title,
            "description": description,
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
