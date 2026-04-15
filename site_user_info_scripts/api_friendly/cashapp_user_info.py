#!/usr/bin/env python3
"""Fetch Cash App profile data by cashtag from rendered HTML page state."""

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

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


SCRIPT_NEXT_DATA = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
SCRIPT_INITIAL_STATE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*({.*?});",
    re.IGNORECASE | re.DOTALL,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Cash App profile info by cashtag.")
    parser.add_argument("username", help="Cash App cashtag with or without leading $")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _collect_dicts(value, out: list[dict]):
    if isinstance(value, dict):
        out.append(value)
        for item in value.values():
            _collect_dicts(item, out)
    elif isinstance(value, list):
        for item in value:
            _collect_dicts(item, out)


def _score_profile_candidate(candidate: dict) -> int:
    score = 0
    key_weights = {
        "cashtag": 4,
        "formatted_cashtag": 4,
        "display_name": 3,
        "avatar_url": 2,
        "country_code": 1,
        "code": 1,
        "bio": 1,
    }
    for key, weight in key_weights.items():
        if key in candidate:
            score += weight
    return score


def _extract_json_blobs(html: str) -> list[dict]:
    blobs: list[dict] = []

    for match in SCRIPT_NEXT_DATA.findall(html):
        text = match.strip()
        if not text:
            continue
        try:
            blobs.append(json.loads(text))
        except json.JSONDecodeError:
            continue

    for match in SCRIPT_INITIAL_STATE.findall(html):
        text = match.strip()
        if not text:
            continue
        try:
            blobs.append(json.loads(text))
        except json.JSONDecodeError:
            continue

    return blobs


def _extract_profile_from_blobs(blobs: list[dict]) -> dict | None:
    dicts: list[dict] = []
    for blob in blobs:
        _collect_dicts(blob, dicts)

    best: dict | None = None
    best_score = -1
    for candidate in dicts:
        score = _score_profile_candidate(candidate)
        if score > best_score:
            best = candidate
            best_score = score

    if best_score <= 0:
        return None
    return best


def main() -> int:
    args = parse_args()
    cashtag = args.username.lstrip("$")
    endpoint = f"https://cash.app/${cashtag}"

    try:
        html = fetch_text(
            endpoint,
            timeout=args.timeout,
            headers={
                "User-Agent": BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        blobs = _extract_json_blobs(html)
        profile = _extract_profile_from_blobs(blobs)
        if profile is None:
            raise RuntimeError("Could not extract structured profile data from Cash App page.")

        result = {
            "site": "CashApp",
            "endpoint": endpoint,
            "lookup": cashtag,
            "cashtag": profile.get("cashtag") or profile.get("formatted_cashtag") or f"${cashtag}",
            "display_name": profile.get("display_name") or profile.get("displayName") or profile.get("name"),
            "bio": profile.get("bio"),
            "avatar_url": profile.get("avatar_url") or profile.get("avatarUrl") or profile.get("avatar"),
            "country_code": profile.get("country_code") or profile.get("countryCode"),
            "code": profile.get("code"),
            "profile_url": endpoint,
            "note": "Cash App has no clean public username API; data is extracted from embedded page state.",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
