#!/usr/bin/env python3
"""Fetch user profile information from Rajce.net (JSON-LD scraper, subdomain URL)."""

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


def _interaction_count(stats: list[dict], interaction_type: str) -> int | None:
    suffix = interaction_type.split("/")[-1]
    for entry in stats:
        if entry.get("interactionType", "").endswith(suffix):
            return entry.get("userInteractionCount")
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Rajce.net user info by username.")
    parser.add_argument("username", help="Rajce.net username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://{args.username}.rajce.idnes.cz/"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        json_ld_m = re.search(
            r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
            html,
            re.DOTALL | re.I,
        )
        if not json_ld_m:
            raise RuntimeError("No JSON-LD found in page.")

        ld = json.loads(json_ld_m.group(1))
        if ld.get("@type") != "ProfilePage":
            raise RuntimeError("Unexpected JSON-LD type.")

        entity = ld.get("mainEntity") or {}
        agent_stats = entity.get("agentInteractionStatistic") or []
        interaction_stats = entity.get("interactionStatistic") or []

        # agent = actions the user has taken; interaction = actions others took on the user
        photos_uploaded = _interaction_count(agent_stats, "WriteAction")
        likes_given = _interaction_count(agent_stats, "LikeAction")
        users_following = _interaction_count(agent_stats, "FollowAction")

        followers = _interaction_count(interaction_stats, "FollowAction")

        # Album count from description meta or og:description
        def _meta(name: str, attr: str = "name") -> str | None:
            for pat in [
                rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
                rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
            ]:
                m = re.search(pat, html, re.I)
                if m:
                    return m.group(1).strip()
            return None

        description = _meta("description") or _meta("og:description", "property")
        album_m = re.search(r"(\d+)\s*alb", description or "", re.I)

        result = {
            "site": "Rajce.net",
            "username": entity.get("alternateName") or args.username,
            "display_name": entity.get("name"),
            "created_at": ld.get("dateCreated"),
            "album_count": int(album_m.group(1)) if album_m else None,
            "photos_uploaded": photos_uploaded,
            "likes_given": likes_given,
            "users_following": users_following,
            "followers": followers,
            "description": description,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
