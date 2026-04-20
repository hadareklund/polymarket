#!/usr/bin/env python3
"""Fetch Steam Community group info via the public XML API (no API key required)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _cdata(xml: str, tag: str) -> str | None:
    m = re.search(rf"<{tag}>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</{tag}>", xml, re.I | re.S)
    return m.group(1).strip() or None if m else None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get Steam Community group info by group name (no API key needed)."
    )
    parser.add_argument("username", help="Steam group URL name")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://steamcommunity.com/groups/{args.username}/memberslistxml/?xml=1"
        xml = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if "<error>" in xml:
            raise RuntimeError(_cdata(xml, "error") or "Group not found.")
        if "<groupID64>" not in xml:
            raise RuntimeError("Group not found or response malformed.")

        member_count_m = re.search(r"<memberCount>(\d+)</memberCount>", xml)
        result = {
            "site": "Steam Community (Group)",
            "group_id64": _cdata(xml, "groupID64"),
            "group_name": _cdata(xml, "groupName"),
            "group_url": _cdata(xml, "groupURL"),
            "headline": _cdata(xml, "headline"),
            "summary": re.sub(r"<[^>]+>", "", _cdata(xml, "summary") or "").strip() or None,
            "member_count": int(member_count_m.group(1)) if member_count_m else None,
            "avatar_url": _cdata(xml, "avatarFull"),
            "profile_url": f"https://steamcommunity.com/groups/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
