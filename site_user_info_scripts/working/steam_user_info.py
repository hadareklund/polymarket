#!/usr/bin/env python3
"""Fetch Steam user profile via the public community XML API (no API key required)."""

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
        description="Get Steam user info by vanity URL (no API key needed)."
    )
    parser.add_argument("username", help="Steam vanity URL username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        url = f"https://steamcommunity.com/id/{args.username}/?xml=1"
        xml = fetch_text(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)
        if "<error>" in xml:
            raise RuntimeError(_cdata(xml, "error") or "User not found.")

        result = {
            "site": "Steam",
            "steam_id64": _cdata(xml, "steamID64"),
            "username": _cdata(xml, "steamID"),
            "online_state": _cdata(xml, "onlineState"),
            "privacy_state": _cdata(xml, "privacyState"),
            "vac_banned": _cdata(xml, "vacBanned") == "1",
            "limited_account": _cdata(xml, "isLimitedAccount") == "1",
            "avatar_url": _cdata(xml, "avatarFull"),
            "profile_url": f"https://steamcommunity.com/id/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
