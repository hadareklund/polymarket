#!/usr/bin/env python3
"""Fetch user profile information from LinuxFR.org (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get LinuxFR.org user info by username.")
    parser.add_argument("username", help="LinuxFR.org username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://linuxfr.org/users/{args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Title: "{username} a écrit {n} contenus de type dépêche ou journal - LinuxFr.org"
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title = title_m.group(1).strip() if title_m else None

        content_count = None
        if title:
            count_m = re.search(r"a écrit (\d+) contenus", title)
            if count_m:
                content_count = int(count_m.group(1))

        # Avatar from LinuxFR CDN
        avatar_m = re.search(r'src="(https?://img\.linuxfr\.org/avatars/[^"]+)"', html)
        if not avatar_m:
            avatar_m = re.search(r'src="(//img\.linuxfr\.org/avatars/[^"]+)"', html)
        avatar_url = avatar_m.group(1) if avatar_m else None
        if avatar_url and avatar_url.startswith("//"):
            avatar_url = "https:" + avatar_url

        result = {
            "site": "LinuxFR.org",
            "username": args.username,
            "content_count": content_count,
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
