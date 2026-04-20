#!/usr/bin/env python3
"""Fetch user profile information from Academia.edu (HTML scraper)."""

from __future__ import annotations

import argparse
import json
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


def _json_ld(html: str) -> dict:
    m = re.search(r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html, re.I | re.S)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Academia.edu user info by username.")
    parser.add_argument("username", help="Academia.edu username (e.g. JohnSmith or institution:JohnSmith)")
    parser.add_argument("--institution", default="independent", help="Institution subdomain (default: independent)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        # Profiles live at <institution>.academia.edu/<Name>
        url = f"https://{args.institution}.academia.edu/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        if "sign_up" in html.lower() and len(html) < 5000:
            raise RuntimeError("Redirected to login/sign-up wall.")

        ld = _json_ld(html)
        title_tag = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)

        result = {
            "site": "Academia.edu",
            "institution": args.institution,
            "username": args.username,
            "name": ld.get("name") or _meta(html, "og:title", "property"),
            "description": ld.get("description") or _meta(html, "description") or _meta(html, "og:description", "property"),
            "avatar_url": ld.get("image") or _meta(html, "og:image", "property"),
            "title": title_tag.group(1).strip() if title_tag else None,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
