#!/usr/bin/env python3
"""Fetch user profile information from Typeracer (HTML scraper)."""

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


def _extract_stats(html: str) -> dict:
    stats: dict = {}
    blocks = re.findall(
        r'<span class="Stat__Top">(.*?)</span>\s*<span class="Stat__Btm">(.*?)<(?:span|/)',
        html,
        re.DOTALL,
    )
    for val, label in blocks:
        stats[label.strip()] = val.strip()
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Typeracer user info by username.")
    parser.add_argument("username", help="Typeracer username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://data.typeracer.com/pit/profile?user={args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        title_text = title_m.group(1).strip() if title_m else ""
        if "Profile Not Found" in title_text:
            raise RuntimeError(f"User '{args.username}' not found on Typeracer.")

        display_name: str | None = None
        parsed = re.match(r"^(.+)\s+\((.+)\)\s+\(TypeRacer", title_text)
        if parsed:
            display_name = parsed.group(1).strip()

        stats = _extract_stats(html)
        result = {
            "site": "Typeracer",
            "username": args.username,
            "display_name": display_name,
            "avg_speed_wpm": stats.get("Full Avg."),
            "best_speed_wpm": stats.get("Best Race"),
            "races": stats.get("Races"),
            "skill_level": stats.get("Skill Level"),
            "exp_level": stats.get("Exp Level"),
            "avatar_url": _meta(html, "og:image", "property"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
