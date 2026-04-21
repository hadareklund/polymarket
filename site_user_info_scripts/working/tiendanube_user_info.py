#!/usr/bin/env python3
"""Fetch store profile information from Tiendanube / Nuvemshop (HTML scraper).

Tiendanube stores are hosted at {store}.mitiendanube.com (ES) or
{store}.lojanuvem.com.br (PT). The username argument is the store slug.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_text, print_json


def _meta(html: str, name: str, attr: str = "name") -> str | None:
    for pattern in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None


_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

DOMAINS = [
    "mitiendanube.com",
    "lojanuvem.com.br",
]


def _try_fetch(store: str, timeout: int) -> tuple[str, str]:
    """Try each Tiendanube domain variant, return (html, url) for the first that works."""
    last_err: Exception | None = None
    for domain in DOMAINS:
        url = f"https://{store}.{domain}"
        try:
            html = fetch_text(url, headers=_HEADERS, timeout=timeout)
            if len(html) > 500:
                return html, url
        except Exception as exc:
            last_err = exc
    raise RuntimeError(f"No accessible Tiendanube store found for '{store}': {last_err}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Tiendanube store info by store slug.")
    parser.add_argument("username", help="Tiendanube store slug (subdomain)")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        html, url = _try_fetch(args.username, args.timeout)
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        result = {
            "site": "Tiendanube",
            "username": args.username,
            "store_name": _meta(html, "og:title", "property") or (title_m.group(1).strip() if title_m else None),
            "description": _meta(html, "og:description", "property") or _meta(html, "description"),
            "logo_url": _meta(html, "og:image", "property"),
            "profile_url": url,
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
