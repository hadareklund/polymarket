#!/usr/bin/env python3
"""Fetch user profile information from Pikabu (HTML scraper, windows-1251 encoding)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import print_json


def _meta(html: str, name: str, attr: str = "name") -> str | None:
    for pattern in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def _fetch_html(url: str, timeout: int) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"})
    with urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
        ct = resp.headers.get("Content-Type", "")
    m = re.search(r"charset=([^\s;]+)", ct, re.I)
    charset = m.group(1) if m else "utf-8"
    return raw.decode(charset, errors="replace")


def _parse_stats(description: str | None) -> dict:
    if not description:
        return {}
    stats: dict = {}
    for m in re.finditer(r"(\d[\d\s]*)\s+(пост\w*|комментари\w*|подписчик\w*)", description):
        count = int(m.group(1).replace("\xa0", "").replace(" ", ""))
        label = m.group(2)
        if label.startswith("пост"):
            stats["post_count"] = count
        elif label.startswith("комментари"):
            stats["comment_count"] = count
        elif label.startswith("подписчик"):
            stats["follower_count"] = count
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Pikabu user info by username.")
    parser.add_argument("username", help="Pikabu username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://pikabu.ru/@{args.username}"
        html = _fetch_html(url, args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        og_title = _meta(html, "og:title", "property")
        og_image = _meta(html, "og:image", "property")
        og_desc = _meta(html, "og:description", "property")
        description = _meta(html, "description")
        stats = _parse_stats(og_desc)
        result = {
            "site": "Pikabu",
            "username": args.username,
            "display_name": og_title,
            "description": description,
            "avatar_url": og_image,
            "post_count": stats.get("post_count"),
            "comment_count": stats.get("comment_count"),
            "follower_count": stats.get("follower_count"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
