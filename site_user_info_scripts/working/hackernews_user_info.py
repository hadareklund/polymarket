#!/usr/bin/env python3
"""Fetch user profile information from Hacker News public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json, unix_to_iso


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Hacker News user info by username.")
    parser.add_argument("username", help="Hacker News username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _fetch_recent_stories(submitted_ids: list[int], timeout: int, max_stories: int = 10) -> list[dict]:
    """Walk submitted item IDs newest-first and collect top-level stories."""
    from urllib.parse import urlparse
    stories: list[dict] = []
    checked = 0
    for item_id in submitted_ids:
        if len(stories) >= max_stories or checked >= 60:
            break
        checked += 1
        try:
            item = fetch_json(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json",
                timeout=timeout,
            )
        except Exception:
            continue
        if not item or item.get("type") != "story" or item.get("deleted") or not item.get("title"):
            continue
        url = item.get("url") or ""
        domain = urlparse(url).netloc.lstrip("www.") if url else None
        stories.append({
            "title": item.get("title"),
            "url": url or None,
            "domain": domain,
            "score": item.get("score"),
            "comments": item.get("descendants"),
            "time": unix_to_iso(item.get("time")),
            "hn_url": f"https://news.ycombinator.com/item?id={item_id}",
        })
    return stories


def main() -> int:
    args = parse_args()
    endpoint = (
        f"https://hacker-news.firebaseio.com/v0/user/{quote(args.username)}.json"
    )
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        if data is None:
            raise RuntimeError("User not found.")
        submitted = data.get("submitted") or []

        recent_stories = _fetch_recent_stories(submitted, args.timeout)
        domains = sorted(
            {s["domain"] for s in recent_stories if s.get("domain")},
        )

        result = {
            "site": "HackerNews",
            "username": data.get("id"),
            "created_unix": data.get("created"),
            "created_at": unix_to_iso(data.get("created")),
            "karma": data.get("karma"),
            "bio": data.get("about"),
            "submission_count": len(submitted),
            "recent_stories": recent_stories,
            "domains_shared": domains,
            "profile_url": f"https://news.ycombinator.com/user?id={quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
