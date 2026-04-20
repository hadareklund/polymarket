#!/usr/bin/env python3
"""Fetch user profile information from AniList (GraphQL)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import print_json

GRAPHQL_URL = "https://graphql.anilist.co"
QUERY = """
query ($username: String) {
  User(name: $username) {
    name
    siteUrl
    about
    avatar { large }
    bannerImage
    createdAt
    updatedAt
    statistics {
      anime { count episodesWatched minutesWatched meanScore }
      manga { count chaptersRead volumesRead meanScore }
    }
    favourites {
      anime { nodes { title { romaji } } }
      manga { nodes { title { romaji } } }
    }
  }
}
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Get AniList user info by username.")
    parser.add_argument("username", help="AniList username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()

    try:
        payload = json.dumps({"query": QUERY, "variables": {"username": args.username}}).encode()
        req = Request(
            GRAPHQL_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "site-user-info-scripts/1.0",
            },
        )
        with urlopen(req, timeout=args.timeout) as r:
            data = json.loads(r.read().decode())

        if "errors" in data:
            msg = data["errors"][0].get("message", "Unknown error")
            raise RuntimeError(f"AniList API error: {msg}")

        u = (data.get("data") or {}).get("User")
        if not u:
            raise RuntimeError("User not found.")

        stats = u.get("statistics") or {}
        anime_stats = stats.get("anime") or {}
        manga_stats = stats.get("manga") or {}
        favs = u.get("favourites") or {}
        fav_anime = [n["title"]["romaji"] for n in (favs.get("anime") or {}).get("nodes", [])[:5]]
        fav_manga = [n["title"]["romaji"] for n in (favs.get("manga") or {}).get("nodes", [])[:5]]

        result = {
            "site": "AniList",
            "username": u.get("name"),
            "bio": u.get("about"),
            "avatar_url": (u.get("avatar") or {}).get("large"),
            "banner_url": u.get("bannerImage"),
            "created_at": u.get("createdAt"),
            "updated_at": u.get("updatedAt"),
            "anime_count": anime_stats.get("count"),
            "anime_episodes_watched": anime_stats.get("episodesWatched"),
            "anime_minutes_watched": anime_stats.get("minutesWatched"),
            "anime_mean_score": anime_stats.get("meanScore"),
            "manga_count": manga_stats.get("count"),
            "manga_chapters_read": manga_stats.get("chaptersRead"),
            "manga_mean_score": manga_stats.get("meanScore"),
            "favourite_anime": fav_anime,
            "favourite_manga": fav_manga,
            "profile_url": u.get("siteUrl"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
