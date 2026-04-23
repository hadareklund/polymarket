#!/usr/bin/env python3
"""Fetch user profile information from LiveJournal (HTML scraper)."""

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


def main() -> int:
    parser = argparse.ArgumentParser(description="Get LiveJournal user info by username.")
    parser.add_argument("username", help="LiveJournal username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://www.livejournal.com/profile?user={args.username}"
        html = fetch_text(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"},
            timeout=args.timeout,
        )
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")

        # JSON-LD Blog block: image (avatar), author.name (real name), url (journal URL)
        author_name = None
        avatar_url = None
        journal_url = None
        for m in re.finditer(
            r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
            html, re.DOTALL | re.I,
        ):
            try:
                ld = json.loads(m.group(1))
                if ld.get("@type") == "Blog":
                    author_name = (ld.get("author") or {}).get("name")
                    avatar_url = ld.get("image")
                    journal_url = ld.get("url")
                    break
            except (json.JSONDecodeError, AttributeError):
                pass

        # Keywords meta: "ЖЖ, LiveJournal, живой журнал, {journal_title}, {real_name}"
        journal_title = None
        kw_m = re.search(r'property="keywords"[^>]+content="([^"]+)"', html)
        if kw_m:
            parts = [p.strip() for p in kw_m.group(1).replace("&#39;", "'").split(",")]
            # parts[3] is the journal title, parts[4] is the real name (if present)
            if len(parts) >= 4:
                journal_title = parts[3] or None
            if not author_name and len(parts) >= 5:
                author_name = parts[4] or None

        # Site.page JSON for achievements count and avatar fallback
        achievements_count = None
        sp_m = re.search(r"Site\.page\s*=\s*(\{.*?\});", html, re.DOTALL)
        if sp_m:
            try:
                sp = json.loads(sp_m.group(1))
                achievements_count = sp.get("achievements_count")
                if not avatar_url:
                    active_key = sp.get("activeuserpic")
                    for pic in sp.get("userpics", []):
                        if pic.get("default") == 1 or pic.get("key") == active_key:
                            avatar_url = pic.get("src")
                            break
            except (json.JSONDecodeError, AttributeError):
                pass

        result = {
            "site": "LiveJournal",
            "username": args.username,
            "display_name": author_name,
            "journal_title": journal_title,
            "journal_url": journal_url or f"https://{args.username}.livejournal.com",
            "avatar_url": avatar_url,
            "achievements_count": achievements_count,
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
