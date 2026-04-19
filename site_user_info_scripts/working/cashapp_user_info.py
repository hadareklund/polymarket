#!/usr/bin/env python3
"""Fetch Cash App profile data by cashtag using a headless browser."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Cash App profile info by cashtag.")
    parser.add_argument("username", help="Cash App cashtag with or without leading $")
    parser.add_argument("--timeout", type=int, default=20, help="Page load timeout in seconds")
    return parser.parse_args()


def _scrape(cashtag: str, timeout_ms: int) -> dict:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright not installed. Run: pip install playwright && python3 -m playwright install chromium"
        )

    url = f"https://cash.app/${cashtag}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        page.goto(url, wait_until="networkidle", timeout=timeout_ms)

        title = page.title()
        if "not found" in title.lower():
            browser.close()
            raise RuntimeError(f"Cash App user '${cashtag}' not found.")

        # Wait for the profile lines to populate (name + cashtag render async)
        page.wait_for_function(
            "() => (document.getElementById('root')?.innerText || '').split('\\n').filter(l => l.trim()).length > 4",
            timeout=10000,
        )

        info = page.evaluate("""() => {
            const lines = (document.getElementById('root')?.innerText || '')
                .split('\\n')
                .map(l => l.trim())
                .filter(l => l);
            const cashtag_idx = lines.findIndex(l => l.startsWith('$'));
            const display_name = cashtag_idx > 0 ? lines[cashtag_idx - 1] : null;
            const cashtag = cashtag_idx >= 0 ? lines[cashtag_idx] : null;
            const og_image = document.querySelector('meta[property="og:image"]')?.content || null;
            return { display_name, cashtag, og_image };
        }""")

        browser.close()

    # If the display name is the same as the cashtag the user hasn't set a name
    display_name = info.get("display_name")
    if display_name and display_name.lstrip("$").lower() == cashtag.lower():
        display_name = None

    return {
        "site": "CashApp",
        "cashtag": info.get("cashtag") or f"${cashtag}",
        "display_name": display_name,
        "profile_url": url,
        "share_image_url": info.get("og_image"),
    }


def main() -> int:
    args = parse_args()
    cashtag = args.username.lstrip("$")
    try:
        result = _scrape(cashtag, timeout_ms=args.timeout * 1000)
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
