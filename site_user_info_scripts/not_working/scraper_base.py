"""
scraper_base.py — shared utilities for all user-info scrapers.
"""

import importlib
import json, time, random, sys
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

JSON_HEADERS = {**HEADERS, "Accept": "application/json, */*;q=0.8"}


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def jitter(lo=0.5, hi=1.5):
    time.sleep(random.uniform(lo, hi))


def safe_text(el) -> str:
    return el.get_text(strip=True) if el else ""


def get_beautifulsoup():
    """Return BeautifulSoup class if bs4 is installed, otherwise None."""
    try:
        return importlib.import_module("bs4").BeautifulSoup
    except Exception:
        return None


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def err(site: str, reason: str) -> dict:
    return {"site": site, "status": "error", "reason": reason}


def ok(site: str, username: str, data: dict) -> dict:
    return {"site": site, "status": "ok", "username": username, **data}
