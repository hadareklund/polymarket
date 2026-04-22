#!/usr/bin/env python3
"""Fetch user profile information from DCinside Gallog (HTML scraper)."""

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
    parser = argparse.ArgumentParser(description="Get DCinside Gallog user info by username.")
    parser.add_argument("username", help="DCinside gallog ID (e.g. damhiya)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://gallog.dcinside.com/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # 404 page check — real gallog pages embed the gid in JS
        if f'gid={args.username}' not in html:
            raise RuntimeError(f"No gallog found for '{args.username}' on DCinside.")

        # Korean nickname shown in the gallog header
        nick_m = re.search(r'class="nick[^"]*">([^<]+)<', html, re.I)
        nickname = nick_m.group(1).strip() if nick_m else None

        # Profile image URL
        profile_img_m = re.search(
            r'src="(https://[^"]*gallog_upimg[^"]*mode=profile[^"]*)"', html
        )
        if profile_img_m:
            avatar_url = profile_img_m.group(1)
        else:
            avatar_url = f"https://dcimg2.dcinside.co.kr/gallog_upimg.php?mode=profile&gid={args.username}"

        result = {
            "site": "DCinside",
            "username": args.username,
            "nickname": nickname,
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
