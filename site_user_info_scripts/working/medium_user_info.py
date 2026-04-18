#!/usr/bin/env python3
"""Fetch Medium profile and post metadata from the public RSS feed."""

from __future__ import annotations

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Get Medium user info from public RSS feed by username."
    )
    parser.add_argument("username", help="Medium username (without @)")
    parser.add_argument("--max-posts", type=int, default=10, help="Max posts to include")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _text_or_none(elem: ET.Element | None, tag: str) -> str | None:
    if elem is None:
        return None
    node = elem.find(tag)
    if node is None:
        return None
    text = (node.text or "").strip()
    return text or None


def main() -> int:
    args = parse_args()
    endpoint = f"https://medium.com/feed/@{quote(args.username)}"

    try:
        xml_text = fetch_text(
            endpoint,
            timeout=args.timeout,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "application/rss+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
            },
        )

        root = ET.fromstring(xml_text)
        channel = root.find("channel")
        if channel is None:
            raise RuntimeError("Unexpected Medium RSS response format.")

        items = channel.findall("item")
        max_posts = max(0, args.max_posts)
        posts: list[dict[str, str | None]] = []
        for item in items[:max_posts]:
            posts.append(
                {
                    "title": _text_or_none(item, "title"),
                    "link": _text_or_none(item, "link"),
                    "pub_date": _text_or_none(item, "pubDate"),
                    "guid": _text_or_none(item, "guid"),
                }
            )

        result = {
            "site": "Medium",
            "endpoint": endpoint,
            "username": args.username,
            "feed_title": _text_or_none(channel, "title"),
            "feed_description": _text_or_none(channel, "description"),
            "feed_link": _text_or_none(channel, "link"),
            "post_count_returned": len(posts),
            "posts": posts,
            "profile_url": f"https://medium.com/@{quote(args.username)}",
            "note": "Medium JSON endpoints are commonly blocked; this script uses RSS feed data.",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
