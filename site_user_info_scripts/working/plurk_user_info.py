#!/usr/bin/env python3
"""Fetch user profile information from Plurk (HTML scraper + embedded JS)."""

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


def _js_str(block: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*"([^"]*)"', block)
    return m.group(1) if m else None


def _js_num(block: str, key: str) -> str | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*([0-9.]+)', block)
    return m.group(1) if m else None


def _js_bool(block: str, key: str) -> bool | None:
    m = re.search(rf'"{re.escape(key)}"\s*:\s*(true|false|null)', block)
    if not m:
        return None
    return m.group(1) == "true" if m.group(1) != "null" else None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Plurk user info by username.")
    parser.add_argument("username", help="Plurk username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.plurk.com/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        page_user_m = re.search(r'"page_user"\s*:\s*(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})', html)
        if not page_user_m:
            raise RuntimeError("Could not find page_user data in page.")
        block = page_user_m.group(1)

        uid = _js_num(block, "id")
        avatar_num = _js_num(block, "avatar")
        avatar_url = None
        if uid and avatar_num and avatar_num not in ("null", "0"):
            avatar_url = f"https://avatars.plurk.com/{uid}-big{avatar_num}.jpg"
        if not avatar_url:
            avatar_url = _meta(html, "og:image", "property")

        result = {
            "site": "Plurk",
            "username": _js_str(block, "nick_name") or args.username,
            "display_name": _js_str(block, "display_name"),
            "full_name": _js_str(block, "full_name"),
            "location": _js_str(block, "location"),
            "karma": float(_js_num(block, "karma")) if _js_num(block, "karma") else None,
            "verified": _js_bool(block, "verified_account"),
            "status": _js_str(block, "status"),
            "relationship": _js_str(block, "relationship"),
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
