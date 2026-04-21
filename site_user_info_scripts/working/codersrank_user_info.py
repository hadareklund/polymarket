#!/usr/bin/env python3
"""Fetch user profile information from Coders Rank (HTML scraper + NUXT state)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _extract(html: str, key: str) -> str | None:
    m = re.search(rf'{re.escape(key)}:"([^"]*)"', html)
    return m.group(1) if m else None


def _extract_num(html: str, key: str):
    m = re.search(rf'{re.escape(key)}:(-?[\d.]+)', html)
    return float(m.group(1)) if m else None


def _extract_list(html: str, key: str) -> list[str]:
    m = re.search(rf'{re.escape(key)}:\[([^\]]*)\]', html)
    if not m:
        return []
    return re.findall(r'"([^"]+)"', m.group(1))


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
    parser = argparse.ArgumentParser(description="Get Coders Rank user info by username.")
    parser.add_argument("username", help="Coders Rank username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://profile.codersrank.io/user/{args.username}"
        html = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # Extract from NUXT embedded state
        nuxt_m = re.search(r'window\.__NUXT__=\(function\([^)]+\)\{return (.*?)\}\(', html, re.S)
        nuxt_raw = nuxt_m.group(0) if nuxt_m else html

        status = _extract(nuxt_raw, "status")
        if status == "not_found":
            raise RuntimeError(f"User '{args.username}' not found on Coders Rank.")

        full_name = _extract(nuxt_raw, "fullName")
        avatar = _extract(nuxt_raw, "avatar")
        if avatar:
            avatar = avatar.encode("raw_unicode_escape").decode("unicode_escape")
        city = _extract(nuxt_raw, "city")
        country = _extract(nuxt_raw, "country")
        total_score = _extract_num(nuxt_raw, "totalScore")
        position_worldwide = _extract_num(nuxt_raw, "positionWorldWide")
        # Extract language skills from scoreBySkills keys (quoted and unquoted JS keys)
        top_skills: list[str] = []
        sb_idx = nuxt_raw.find("scoreBySkills:{")
        if sb_idx >= 0:
            chunk = nuxt_raw[sb_idx:sb_idx + 3000]
            matches = re.findall(r'"([^"]+)":\{score:|([A-Za-z][\w\s]*):\{score:', chunk)
            top_skills = [q or u.strip() for q, u in matches]

        # Fall back to OG meta tags
        og_title = _meta(html, "og:title", attr="property")
        og_image = _meta(html, "og:image", attr="property")

        result = {
            "site": "Coders Rank",
            "username": args.username,
            "name": full_name,
            "city": city,
            "country": country,
            "total_score": total_score,
            "position_worldwide": int(position_worldwide) if position_worldwide else None,
            "top_skills": top_skills,
            "avatar_url": avatar or og_image,
            "og_title": og_title,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
