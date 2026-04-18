"""
doxbin_user_info.py
Best-effort Doxbin profile metadata scraper.

Notes:
  - Doxbin frequently changes domains and is often protected by Cloudflare.
  - This scraper intentionally extracts only compact public metadata.

Optional environment variables:
  - DOXBIN_BASES: comma-separated base URLs to try first.
      Example: DOXBIN_BASES="https://doxbin.net,https://doxbin.org"
  - DOXBIN_COOKIE: raw Cookie header from a browser session.
      Useful for sites protected by Cloudflare (for example with cf_clearance).
"""

import importlib
import os
import re
import sys

from scraper_base import new_session, ok, err, dump

SITE = "doxbin"
BASE_CANDIDATES = [
    "https://doxbin.com",
    "https://doxbin.net",
]

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


def _get_base_candidates() -> list[str]:
    env_bases = os.environ.get("DOXBIN_BASES", "").strip()
    if not env_bases:
        return BASE_CANDIDATES
    out = []
    for base in env_bases.split(","):
        base = base.strip().rstrip("/")
        if not base:
            continue
        if not base.startswith(("http://", "https://")):
            base = "https://" + base
        out.append(base)
    return out or BASE_CANDIDATES


def _extract_meta(page: str, key: str) -> str | None:
    patterns = [
        rf'<meta\s+name=["\']{re.escape(key)}["\']\s+content=["\']([^"\']*)["\']',
        rf'<meta\s+property=["\']{re.escape(key)}["\']\s+content=["\']([^"\']*)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, page, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def _extract_title(page: str) -> str | None:
    m = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return " ".join(m.group(1).split())


def _parse_counts(page: str) -> dict:
    out = {"posts": None, "followers": None, "following": None}
    patterns = {
        "posts": r"posts?\D{0,20}(\d{1,9})",
        "followers": r"followers?\D{0,20}(\d{1,9})",
        "following": r"following\D{0,20}(\d{1,9})",
    }
    lowered = page.lower()
    for key, pat in patterns.items():
        m = re.search(pat, lowered, re.IGNORECASE)
        if m:
            out[key] = m.group(1)
    return out


def _cloudflare_block(page: str) -> bool:
    markers = [
        "just a moment",
        "cf-challenge",
        "cloudflare",
        "attention required",
        "cf-mitigated",
        "verify you are human",
    ]
    low = page.lower()
    return any(marker in low for marker in markers)


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
                "domain": ".doxbin.net",
                "path": "/",
                "secure": True,
                "httpOnly": False,
            }
        )
    return cookies


def _fetch_with_playwright(
    url: str, cookie_header: str | None
) -> tuple[str | None, str | None]:
    try:
        sync_api = importlib.import_module("playwright.sync_api")
        sync_playwright = sync_api.sync_playwright
    except Exception:
        return (
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
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            html = page.content()
            context.close()
            browser.close()
            return html, None
    except Exception as e:
        return None, f"Playwright fetch failed: {e}"


def scrape(username: str) -> dict:
    s = new_session()
    s.headers.update(EXTRA_BROWSER_HEADERS)

    cookie = os.environ.get("DOXBIN_COOKIE")
    if cookie:
        s.headers.update(
            {
                "Cookie": cookie,
                "Referer": "https://doxbin.net/",
            }
        )

    attempts: list[dict] = []
    for base in _get_base_candidates():
        for path in [f"/user/{username}", f"/profile/{username}", f"/@{username}"]:
            url = f"{base}{path}"
            try:
                r = s.get(url, timeout=15)
            except Exception as e:
                attempts.append({"url": url, "status": "error", "reason": str(e)})
                continue

            page = r.text or ""
            if r.status_code in (301, 302):
                attempts.append(
                    {
                        "url": url,
                        "status": "redirect",
                        "location": r.headers.get("Location"),
                    }
                )
                continue

            if r.status_code == 404:
                attempts.append({"url": url, "status": "not_found"})
                continue

            if r.status_code in (403, 429) or _cloudflare_block(page):
                html_pw, pw_error = _fetch_with_playwright(url, cookie)
                if html_pw and not _cloudflare_block(html_pw):
                    page = html_pw
                    attempts.append(
                        {
                            "url": url,
                            "status": "used_playwright",
                            "reason": "Bypassed request-level block",
                        }
                    )
                else:
                    reason = f"HTTP {r.status_code} / Cloudflare challenge"
                    if pw_error:
                        reason = f"{reason}; {pw_error}"
                    attempts.append(
                        {
                            "url": url,
                            "status": "blocked",
                            "reason": reason,
                        }
                    )
                    continue

            if r.status_code != 200:
                attempts.append(
                    {
                        "url": url,
                        "status": "error",
                        "reason": f"HTTP {r.status_code}",
                    }
                )
                continue

            title = _extract_title(page)
            desc = _extract_meta(page, "description") or _extract_meta(
                page, "og:description"
            )
            counts = _parse_counts(page)

            data = {
                "url": url,
                "username": username,
                "title": title,
                "description": desc,
                "posts": counts.get("posts"),
                "followers": counts.get("followers"),
                "following": counts.get("following"),
                "note": "Best-effort metadata only; Doxbin often blocks automated requests.",
            }
            return ok(SITE, username, data)

    return err(
        SITE,
        "no accessible Doxbin profile endpoint found; likely DNS/Cloudflare/domain drift. Try DOXBIN_BASES and/or DOXBIN_COOKIE.",
    ) | {"attempts": attempts[:10]}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "test"
    print(dump(scrape(target)))
