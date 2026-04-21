#!/usr/bin/env python3
"""Fetch user profile information from Open Collective via its public GraphQL API."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import print_json

_GQL_URL = "https://api.opencollective.com/graphql/v2"
_QUERY = """
query($slug: String!) {
  account(slug: $slug) {
    name
    slug
    description
    website
    twitterHandle
    githubHandle
    imageUrl
    type
  }
}
"""


def gql(slug: str, timeout: int) -> dict:
    payload = json.dumps({"query": _QUERY, "variables": {"slug": slug}}).encode()
    req = Request(
        _GQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Open Collective user info by slug.")
    parser.add_argument("username", help="Open Collective slug/username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        resp = gql(args.username, args.timeout)
        if "errors" in resp:
            raise RuntimeError(resp["errors"][0].get("message", "GraphQL error"))
        acct = (resp.get("data") or {}).get("account")
        if not acct:
            raise RuntimeError("Account not found.")
        result = {
            "site": "Open Collective",
            "username": acct.get("slug"),
            "name": acct.get("name"),
            "type": acct.get("type"),
            "description": acct.get("description"),
            "website": acct.get("website"),
            "twitter": acct.get("twitterHandle"),
            "github": acct.get("githubHandle"),
            "avatar_url": acct.get("imageUrl"),
            "profile_url": f"https://opencollective.com/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
