#!/usr/bin/env python3
"""Aggregate user info across implemented API collectors and append to a text file."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote

from common import fetch_json, load_env_file, unix_to_iso


def collect_github(username: str, timeout: int) -> dict[str, Any]:
    endpoint = f"https://api.github.com/users/{quote(username)}"
    data = fetch_json(endpoint, timeout=timeout)
    return {
        "endpoint": endpoint,
        "username": data.get("login"),
        "name": data.get("name"),
        "bio": data.get("bio"),
        "company": data.get("company"),
        "location": data.get("location"),
        "email": data.get("email"),
        "blog": data.get("blog"),
        "public_repos": data.get("public_repos"),
        "followers": data.get("followers"),
        "following": data.get("following"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "profile_url": data.get("html_url"),
    }


def collect_hackernews(username: str, timeout: int) -> dict[str, Any]:
    endpoint = f"https://hacker-news.firebaseio.com/v0/user/{quote(username)}.json"
    data = fetch_json(endpoint, timeout=timeout)
    if data is None:
        raise RuntimeError("User not found")
    submitted = data.get("submitted") or []
    return {
        "endpoint": endpoint,
        "username": data.get("id"),
        "created_unix": data.get("created"),
        "created_at": unix_to_iso(data.get("created")),
        "karma": data.get("karma"),
        "bio": data.get("about"),
        "submission_count": len(submitted),
        "profile_url": f"https://news.ycombinator.com/user?id={quote(username)}",
    }


def _compact_keybase_proofs(proofs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    for proof in proofs:
        compact.append(
            {
                "type": proof.get("proof_type"),
                "username": proof.get("nametag"),
                "state": proof.get("state"),
                "service_url": proof.get("service_url"),
            }
        )
    return compact


def collect_keybase(username: str, timeout: int) -> dict[str, Any]:
    endpoint = (
        "https://keybase.io/_/api/1.0/user/lookup.json" f"?usernames={quote(username)}"
    )
    data = fetch_json(endpoint, timeout=timeout)
    them = data.get("them") or []
    if not them:
        raise RuntimeError("User not found")
    user = them[0]
    basics = user.get("basics") or {}
    profile = user.get("profile") or {}
    proofs_summary = user.get("proofs_summary") or {}
    proofs = proofs_summary.get("all") or []
    return {
        "endpoint": endpoint,
        "username": basics.get("username") or username,
        "full_name": profile.get("full_name"),
        "bio": profile.get("bio"),
        "location": profile.get("location"),
        "proofs": _compact_keybase_proofs(proofs),
        "cryptocurrency_addresses": user.get("cryptocurrency_addresses") or [],
        "public_keys": user.get("public_keys") or {},
        "profile_url": f"https://keybase.io/{quote(username)}",
    }


def _country_from_url(country_url: str | None) -> str | None:
    if not country_url or "/" not in country_url:
        return None
    return country_url.rstrip("/").split("/")[-1]


def collect_chesscom(username: str, timeout: int) -> dict[str, Any]:
    endpoint = f"https://api.chess.com/pub/player/{quote(username)}"
    data = fetch_json(endpoint, timeout=timeout)
    return {
        "endpoint": endpoint,
        "username": data.get("username"),
        "name": data.get("name"),
        "location": data.get("location"),
        "country_code": _country_from_url(data.get("country")),
        "country_url": data.get("country"),
        "status": data.get("status"),
        "joined_unix": data.get("joined"),
        "joined_at": unix_to_iso(data.get("joined")),
        "last_online_unix": data.get("last_online"),
        "last_online_at": unix_to_iso(data.get("last_online")),
        "twitch_url": data.get("twitch_url"),
        "profile_url": data.get("url"),
    }


def collect_mixcloud(username: str, timeout: int) -> dict[str, Any]:
    endpoint = f"https://api.mixcloud.com/{quote(username)}/"
    data = fetch_json(endpoint, timeout=timeout)
    return {
        "endpoint": endpoint,
        "username": data.get("username"),
        "display_name": data.get("name"),
        "bio": data.get("biog"),
        "city": data.get("city"),
        "country": data.get("country"),
        "follower_count": data.get("follower_count"),
        "following_count": data.get("following_count"),
        "is_pro": data.get("is_pro"),
        "pictures": data.get("pictures"),
        "profile_url": data.get("url")
        or f"https://www.mixcloud.com/{quote(username)}/",
    }


def collect_reddit(
    username: str,
    timeout: int,
    access_token: str,
    user_agent: str,
) -> dict[str, Any]:
    endpoint = f"https://oauth.reddit.com/user/{quote(username)}/about"
    data = fetch_json(
        endpoint,
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": user_agent,
        },
    )
    profile = data.get("data") or {}
    subreddit = profile.get("subreddit") or {}
    return {
        "endpoint": endpoint,
        "username": profile.get("name") or username,
        "id": profile.get("id"),
        "created_utc": profile.get("created_utc"),
        "created_at": unix_to_iso(profile.get("created_utc")),
        "comment_karma": profile.get("comment_karma"),
        "link_karma": profile.get("link_karma"),
        "total_karma": (profile.get("comment_karma") or 0)
        + (profile.get("link_karma") or 0),
        "is_gold": profile.get("is_gold"),
        "is_mod": profile.get("is_mod"),
        "bio": subreddit.get("public_description") or subreddit.get("description"),
        "profile_url": f"https://www.reddit.com/user/{quote(username)}/",
    }


def collect_stackoverflow(
    username: str,
    timeout: int,
    api_key: str | None,
    pagesize: int,
) -> dict[str, Any]:
    endpoint = "https://api.stackexchange.com/2.3/users"
    params = {
        "inname": username,
        "site": "stackoverflow",
        "order": "desc",
        "sort": "reputation",
        "pagesize": max(1, min(pagesize, 100)),
        "key": api_key,
    }
    data = fetch_json(endpoint, timeout=timeout, params=params)
    items = data.get("items") or []

    compact_items: list[dict[str, Any]] = []
    for item in items:
        compact_items.append(
            {
                "user_id": item.get("user_id"),
                "display_name": item.get("display_name"),
                "reputation": item.get("reputation"),
                "badges": item.get("badge_counts"),
                "website_url": item.get("website_url"),
                "location": item.get("location"),
                "creation_date": unix_to_iso(item.get("creation_date")),
                "last_access_date": unix_to_iso(item.get("last_access_date")),
                "profile_url": item.get("link"),
            }
        )

    return {
        "endpoint": endpoint,
        "query": username,
        "match_count": len(items),
        "has_more": data.get("has_more"),
        "quota_remaining": data.get("quota_remaining"),
        "results": compact_items,
    }


def collect_twitter(username: str, timeout: int, bearer_token: str) -> dict[str, Any]:
    endpoint = f"https://api.twitter.com/2/users/by/username/{quote(username)}"
    params = {
        "user.fields": "created_at,description,location,name,profile_image_url,public_metrics,url,verified"
    }
    data = fetch_json(
        endpoint,
        timeout=timeout,
        params=params,
        headers={"Authorization": f"Bearer {bearer_token}"},
    )
    profile = data.get("data") or {}
    metrics = profile.get("public_metrics") or {}
    return {
        "endpoint": endpoint,
        "username": profile.get("username") or username,
        "id": profile.get("id"),
        "name": profile.get("name"),
        "description": profile.get("description"),
        "location": profile.get("location"),
        "created_at": profile.get("created_at"),
        "verified": profile.get("verified"),
        "followers_count": metrics.get("followers_count"),
        "following_count": metrics.get("following_count"),
        "tweet_count": metrics.get("tweet_count"),
        "listed_count": metrics.get("listed_count"),
        "profile_url": profile.get("url") or f"https://x.com/{quote(username)}",
        "api_errors": data.get("errors"),
    }


def run_collector(
    site_name: str, runner: Callable[[], dict[str, Any]]
) -> dict[str, Any]:
    try:
        return {"status": "ok", "data": runner()}
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def append_record(output_path: Path, record: dict[str, Any]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as handle:
        handle.write("=== USER_INFO_RECORD_START ===\n")
        handle.write(json.dumps(record, indent=2, sort_keys=False))
        handle.write("\n=== USER_INFO_RECORD_END ===\n\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect user info from implemented API-based site scripts and append "
            "one structured record to a text file."
        )
    )
    parser.add_argument("username", help="Target username to query across sites")
    parser.add_argument(
        "--output",
        default="site_user_info_scripts/user_info_records.txt",
        help="Structured text output path (append mode)",
    )
    parser.add_argument(
        "--timeout", type=int, default=20, help="HTTP timeout in seconds"
    )

    parser.add_argument(
        "--reddit-access-token",
        help="Reddit OAuth token (or set REDDIT_ACCESS_TOKEN in env or .env)",
    )
    parser.add_argument(
        "--reddit-user-agent",
        default="site-user-info-scripts/1.0",
        help="Reddit API User-Agent",
    )
    parser.add_argument(
        "--stackexchange-api-key",
        help="StackExchange API key (or set STACKEXCHANGE_API_KEY in env or .env)",
    )
    parser.add_argument("--stackoverflow-pagesize", type=int, default=10)
    parser.add_argument(
        "--twitter-bearer-token",
        help="Twitter/X bearer token (or set TWITTER_BEARER_TOKEN in env or .env)",
    )

    return parser.parse_args()


def main() -> int:
    load_env_file(start_dir=Path(__file__).resolve().parent)
    args = parse_args()

    if args.timeout <= 0:
        print("Error: --timeout must be > 0", file=sys.stderr)
        return 2

    username = args.username
    reddit_token = args.reddit_access_token or os.getenv("REDDIT_ACCESS_TOKEN")
    stackexchange_key = args.stackexchange_api_key or os.getenv("STACKEXCHANGE_API_KEY")
    twitter_token = args.twitter_bearer_token or os.getenv("TWITTER_BEARER_TOKEN")

    sites: dict[str, dict[str, Any]] = {}

    sites["GitHub"] = run_collector(
        "GitHub", lambda: collect_github(username=username, timeout=args.timeout)
    )
    sites["HackerNews"] = run_collector(
        "HackerNews",
        lambda: collect_hackernews(username=username, timeout=args.timeout),
    )
    sites["Keybase"] = run_collector(
        "Keybase", lambda: collect_keybase(username=username, timeout=args.timeout)
    )
    sites["chess.com"] = run_collector(
        "chess.com", lambda: collect_chesscom(username=username, timeout=args.timeout)
    )
    sites["Mixcloud"] = run_collector(
        "Mixcloud", lambda: collect_mixcloud(username=username, timeout=args.timeout)
    )

    if reddit_token:
        sites["Reddit"] = run_collector(
            "Reddit",
            lambda: collect_reddit(
                username=username,
                timeout=args.timeout,
                access_token=reddit_token,
                user_agent=args.reddit_user_agent,
            ),
        )
    else:
        sites["Reddit"] = {
            "status": "skipped",
            "reason": "Missing REDDIT_ACCESS_TOKEN or --reddit-access-token",
        }

    sites["StackOverflow"] = run_collector(
        "StackOverflow",
        lambda: collect_stackoverflow(
            username=username,
            timeout=args.timeout,
            api_key=stackexchange_key,
            pagesize=args.stackoverflow_pagesize,
        ),
    )

    if twitter_token:
        sites["Twitter"] = run_collector(
            "Twitter",
            lambda: collect_twitter(
                username=username,
                timeout=args.timeout,
                bearer_token=twitter_token,
            ),
        )
    else:
        sites["Twitter"] = {
            "status": "skipped",
            "reason": "Missing TWITTER_BEARER_TOKEN or --twitter-bearer-token",
        }

    ok_count = sum(1 for item in sites.values() if item.get("status") == "ok")
    error_count = sum(1 for item in sites.values() if item.get("status") == "error")
    skipped_count = sum(1 for item in sites.values() if item.get("status") == "skipped")

    record = {
        "run_at_utc": datetime.now(tz=timezone.utc).isoformat(),
        "username": username,
        "summary": {
            "ok": ok_count,
            "error": error_count,
            "skipped": skipped_count,
            "total_sites": len(sites),
        },
        "sites": sites,
    }

    output_path = Path(args.output)
    append_record(output_path, record)

    print(f"Appended user record for '{username}' to {output_path}")
    print(
        f"Summary: ok={ok_count}, error={error_count}, skipped={skipped_count}, total={len(sites)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
