#!/usr/bin/env python3
"""Fetch user profile information from AllMyLinks (HTML scraper)."""

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


def _extract_links(html: str) -> list[dict]:
    """Extract social/external links listed on the profile page."""
    links: list[dict] = []
    seen: set[str] = set()
    for m in re.finditer(r'<a\s[^>]*href="(https?://[^"]+)"[^>]*>([^<]*)</a>', html, re.I):
        href, label = m.group(1).strip(), m.group(2).strip()
        if href in seen or not label:
            continue
        seen.add(href)
        links.append({"label": label, "url": href})
    return links[:20]


def main() -> int:
    parser = argparse.ArgumentParser(description="Get AllMyLinks user info by username.")
    parser.add_argument("username", help="AllMyLinks username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        url = f"https://allmylinks.com/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        ld = _json_ld(html)
        title_tag = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        links = _extract_links(html)

        result = {
            "site": "AllMyLinks",
            "username": args.username,
            "name": ld.get("name") or _meta(html, "og:title", "property"),
            "description": ld.get("description") or _meta(html, "description") or _meta(html, "og:description", "property"),
            "avatar_url": ld.get("image") or _meta(html, "og:image", "property"),
            "title": title_tag.group(1).strip() if title_tag else None,
            "links": links,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
