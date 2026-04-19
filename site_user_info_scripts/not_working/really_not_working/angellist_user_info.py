"""
angellist_user_info.py
Scrapes a Wellfound (fmr. AngelList) public profile page.

Optional authenticated mode:
    export WELLFOUND_COOKIE="cf_clearance=...; __cf_bm=...; ..."
    Using browser cookies helps bypass Cloudflare challenges.

Profile URL: https://wellfound.com/u/{username}

Returns fields:
  name, headline, location, bio, avatar_url,
  skills[], roles[], past_companies[], social_links{},
  followers, following, joined_year
"""

import importlib
import os
import sys, re, json
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PARENT_DIR = SCRIPT_DIR.parent
SCRAPE_PENDING_DIR = PARENT_DIR / "scrape_pending"
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))
if str(SCRAPE_PENDING_DIR) not in sys.path:
    sys.path.insert(0, str(SCRAPE_PENDING_DIR))

try:
    from common import load_env_file
except Exception:  # pragma: no cover - optional convenience import
    load_env_file = None

from site_user_info_scripts.not_working.really_not_working.scraper_base import (
    new_session,
    safe_text,
    ok,
    err,
    dump,
    get_beautifulsoup,
)

SITE = "angellist"

EXTRA_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-CH-UA": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def _looks_like_challenge(page: str) -> bool:
    low = (page or "").lower()
    return (
        "please enable js and disable any ad blocker" in low
        or "cf-challenge" in low
        or "cloudflare" in low
        or "dd={'rt':'c'" in low
    )


def _parse_next_data(page_text: str) -> dict | None:
    next_data_match = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        page_text,
        re.IGNORECASE | re.DOTALL,
    )
    if not next_data_match:
        return None
    try:
        return json.loads(next_data_match.group(1))
    except Exception:
        return None


def _extract_user_payload(username: str, url: str, page_text: str) -> dict | None:
    data = _parse_next_data(page_text)
    if not data:
        return None
    user = data.get("props", {}).get("pageProps", {}).get("user") or data.get(
        "props", {}
    ).get("pageProps", {}).get("talent")
    if not user:
        return None

    roles = [r.get("title", "") for r in (user.get("roles") or [])]
    skills = [s.get("name", "") for s in (user.get("skills") or [])]
    past = [c.get("company", {}).get("name", "") for c in (user.get("pastJobs") or [])]

    return {
        "url": url,
        "name": user.get("name"),
        "headline": user.get("roleTitle") or user.get("headline"),
        "location": user.get("location"),
        "bio": user.get("bio"),
        "avatar_url": user.get("avatarUrl"),
        "followers": user.get("followersCount"),
        "following": user.get("followingCount"),
        "roles": roles,
        "skills": skills,
        "past_companies": past,
        "social_links": {
            "twitter": user.get("twitterUrl"),
            "github": user.get("githubUrl"),
            "linkedin": user.get("linkedinUrl"),
            "blog": user.get("blogUrl"),
        },
    }


def _parse_cookie_header(cookie_header: str) -> list[dict]:
    cookies = []
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        name = name.strip()
        value = value.strip()
        if not name:
            continue
        cookies.append(
            {
                "name": name,
                "value": value,
                "domain": ".wellfound.com",
                "path": "/",
                "secure": True,
                "httpOnly": False,
            }
        )
    return cookies


def _fetch_with_playwright(
    url: str, cookie_header: str | None
) -> tuple[str | None, int | None, str | None]:
    try:
        sync_api = importlib.import_module("playwright.sync_api")
        sync_playwright = sync_api.sync_playwright
    except Exception:
        return (
            None,
            None,
            "Playwright not installed. Run: ../../.venv/bin/python -m pip install playwright && ../../.venv/bin/python -m playwright install chromium",
        )

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                extra_http_headers={
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            if cookie_header:
                parsed = _parse_cookie_header(cookie_header)
                if parsed:
                    context.add_cookies(parsed)

            page = context.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            html = page.content()
            context.close()
            browser.close()
            return html, (resp.status if resp else None), None
    except Exception as e:
        return None, None, f"Playwright fetch failed: {e}"


def scrape(username: str) -> dict:
    if load_env_file:
        load_env_file(start_dir=SCRIPT_DIR)

    url = f"https://wellfound.com/u/{username}"
    s = new_session()
    s.headers.update(EXTRA_BROWSER_HEADERS)

    cookie = os.environ.get("WELLFOUND_COOKIE")
    if cookie:
        s.headers.update({"Cookie": cookie, "Referer": "https://wellfound.com/"})

    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code == 403:
        if _looks_like_challenge(r.text):
            html, pw_status, pw_error = _fetch_with_playwright(url, cookie)
            if html:
                if _looks_like_challenge(html) or pw_status == 403:
                    return err(
                        SITE,
                        "blocked by Cloudflare challenge (403) even with Playwright. Export WELLFOUND_COOKIE from a real browser session.",
                    )
                parsed = _extract_user_payload(username, url, html)
                if parsed:
                    return ok(SITE, username, parsed)
                return err(
                    SITE,
                    "Playwright loaded page but profile JSON was not found (possible layout change or non-profile page)",
                )
            if pw_error:
                return err(
                    SITE,
                    "blocked by Cloudflare challenge (403). " + pw_error,
                )
        if cookie:
            return err(SITE, "blocked (403) — WELLFOUND_COOKIE may be expired")
        return err(
            SITE,
            "blocked (403). Set WELLFOUND_COOKIE from a logged-in browser session or use Playwright",
        )
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    parsed = _extract_user_payload(username, url, r.text)
    if parsed:
        return ok(SITE, username, parsed)

    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:
        return err(
            SITE,
            "beautifulsoup4 not installed and __NEXT_DATA__ unavailable for fallback parsing",
        )

    soup = BeautifulSoup(r.text, "lxml")

    # ── Fallback: HTML parsing ──────────────────────────────────────────────
    name = safe_text(soup.find("h1"))
    headline = safe_text(soup.select_one("div[class*='headline'], div[class*='role']"))
    location = safe_text(soup.select_one("span[class*='location']"))
    bio = safe_text(soup.select_one("div[class*='bio'], p[class*='about']"))

    skills = [
        safe_text(t) for t in soup.select("a[class*='skill'], span[class*='skill']")
    ]
    socials = {}
    for a in soup.select(
        "a[href*='twitter.com'], a[href*='github.com'], a[href*='linkedin.com']"
    ):
        href = a.get("href", "")
        if "twitter" in href:
            socials["twitter"] = href
        if "github" in href:
            socials["github"] = href
        if "linkedin" in href:
            socials["linkedin"] = href

    if not name:
        return err(SITE, "could not parse profile — site may require JS rendering")

    return ok(
        SITE,
        username,
        {
            "url": url,
            "name": name,
            "headline": headline,
            "location": location,
            "bio": bio,
            "avatar_url": None,
            "followers": None,
            "following": None,
            "roles": [],
            "skills": skills,
            "past_companies": [],
            "social_links": socials,
        },
    )


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "naval"
    print(dump(scrape(username)))
