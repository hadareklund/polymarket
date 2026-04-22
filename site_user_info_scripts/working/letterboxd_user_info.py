#!/usr/bin/env python3
"""Fetch user profile information from Letterboxd (HTML scraper)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _og(html: str, prop: str) -> str | None:
    for pat in [
        rf'<meta[^>]+property="og:{re.escape(prop)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+property="og:{re.escape(prop)}"',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def _meta(html: str, name: str) -> str | None:
    for pat in [
        rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]*)"',
        rf'<meta[^>]+content="([^"]*)"[^>]+name="{re.escape(name)}"',
    ]:
        m = re.search(pat, html, re.I)
        if m:
            return m.group(1).strip()
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Letterboxd user info by username.")
    parser.add_argument("username", help="Letterboxd username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://letterboxd.com/{args.username}/"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        og_title = _og(html, "title")
        description = _meta(html, "description") or _og(html, "description")
        avatar_url = _og(html, "image")

        # Extract display name from description: "{Name} uses Letterboxd to share..."
        display_name = None
        m = re.match(r"^(.+?)\s+uses Letterboxd", description or "")
        if m:
            display_name = m.group(1).strip()
        elif og_title:
            # og:title: "username’s profile • Letterboxd"
            m = re.match(r"^(.+?)(?:’s\s+(?:Films|profile)|'s\s+(?:Films|profile)|\s*[•·|])", og_title)
            display_name = m.group(1).strip() if m else og_title

        # Extract stats from description, e.g. "5 films watched."
        films_watched = None
        if description:
            m = re.search(r"([\d,]+)\s+films?\s+watched", description, re.I)
            if m:
                films_watched = m.group(1).replace(",", "")

        result = {
            "site": "Letterboxd",
            "username": args.username,
            "display_name": display_name,
            "description": description,
            "films_watched": int(films_watched) if films_watched else None,
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
