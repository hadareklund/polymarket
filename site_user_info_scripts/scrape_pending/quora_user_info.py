"""
quora_user_info.py
Scrapes a Quora public profile.

Quora returns 403 to cold requests (Cloudflare + bot detection).
Works in two modes:

  MODE 1 — Session cookie (recommended):
    Export your m-b cookie from a logged-in Quora browser session.
    export QUORA_M_B=your_m-b_cookie_value
        Or export the full cookie header from your browser session.
        export QUORA_COOKIE='m-b=...; __cf_bm=...; ...'
    Returns full profile including follower counts, answer count, etc.

  MODE 2 — Public HTML (cold):
    Often blocked by Cloudflare. Returns partial data if it gets through.

Profile URL: https://www.quora.com/profile/{username}

Returns fields:
  name, username, bio, profile_url, avatar_url,
  followers, following, answers, questions, posts,
  knows_about[], credentials[], social_links{}
"""

import importlib
import sys, os, re, json
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "quora"


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


def _cookie_headers(m_b: str | None, raw_cookie: str | None) -> dict:
    if raw_cookie:
        return {
            "Cookie": raw_cookie,
            "Referer": "https://www.quora.com/",
        }
    if not m_b:
        return {}
    return {
        "Cookie": f"m-b={m_b}",
        "Referer": "https://www.quora.com/",
    }


def _cloudflare_block(page: str) -> bool:
    markers = [
        "just a moment",
        "cf-challenge",
        "cloudflare",
        "attention required",
        "cf-mitigated",
        "verify you are human",
    ]
    low = (page or "").lower()
    return any(marker in low for marker in markers)


def _cookie_dict(m_b: str | None, raw_cookie: str | None) -> dict[str, str]:
    if raw_cookie:
        out: dict[str, str] = {}
        for part in raw_cookie.split(";"):
            if "=" not in part:
                continue
            name, value = part.split("=", 1)
            name = name.strip()
            value = value.strip()
            if name:
                out[name] = value
        if out:
            return out
    if not m_b:
        return {}
    return {"m-b": m_b}


def _fetch_with_playwright(
    url: str, m_b: str | None, raw_cookie: str | None
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
                extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
            )
            cookies = _cookie_dict(m_b, raw_cookie)
            if cookies:
                context.add_cookies(
                    [
                        {
                            "name": name,
                            "value": value,
                            "domain": ".quora.com",
                            "path": "/",
                            "secure": True,
                            "httpOnly": False,
                        }
                        for name, value in cookies.items()
                    ]
                )

            page = context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(3000)
            html = page.content()
            context.close()
            browser.close()
            return html, None
    except Exception as e:
        return None, f"Playwright fetch failed: {e}"


def _parse_profile(html: str, username: str) -> dict:
    # Quora embeds Next.js / Apollo state in window.__APOLLO_STATE__
    for script_match in re.finditer(
        r"<script[^>]*>(.*?)</script>", html, re.IGNORECASE | re.DOTALL
    ):
        text = script_match.group(1) or ""
        if "window.__APOLLO_STATE__" in text or "apolloState" in text:
            # Extract JSON blob
            m = re.search(r'"User:[^"]*":\{(.+?)\}(?:,"|,\n")', text, re.DOTALL)
            if m:
                try:
                    # Try to grab structured state
                    state_m = re.search(
                        r"(?:window\.__APOLLO_STATE__|window\.__STATE__)\s*=\s*(\{.+\})\s*;",
                        text,
                        re.DOTALL,
                    )
                    if state_m:
                        state = json.loads(state_m.group(1))
                        # Find user node
                        for k, v in state.items():
                            if isinstance(v, dict) and v.get("uid") and v.get("names"):
                                names = v.get("names", [{}])
                                return {
                                    "name": names[0].get("text") if names else None,
                                    "bio": v.get("profileBio", {}).get("text"),
                                    "avatar_url": v.get("profileImageUrl"),
                                    "followers": v.get("followerCount"),
                                    "following": v.get("followingCount"),
                                    "answers": v.get("answerCount"),
                                    "questions": v.get("questionCount"),
                                    "posts": v.get("postCount"),
                                    "knows_about": [],
                                }
                except Exception:
                    pass

    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:
        title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_m:
            name = re.sub(r"<[^>]+>", " ", title_m.group(1)).strip()
            return {
                "name": name,
                "bio": None,
                "avatar_url": None,
                "_note": "partial data without beautifulsoup4",
            }
        return {"_error": "beautifulsoup4 not installed; install for HTML fallback"}

    soup = BeautifulSoup(html, "lxml")

    # Fallback: HTML parsing
    name = safe_text(soup.select_one("div[class*='UserName'], span[class*='name']"))
    bio = safe_text(soup.select_one("div[class*='UserBio'], div[class*='bio']"))
    avatar_el = soup.select_one("img[class*='avatar'], img[class*='UserPhoto']")
    avatar = avatar_el.get("src") if avatar_el else None

    # Stats (answers, followers, following)
    stats = {}
    for el in soup.select("a[class*='stat'], div[class*='UserStats'] a"):
        txt = safe_text(el)
        num_m = re.search(r"([\d,.]+[KMB]?)", txt)
        if not num_m:
            continue
        num = num_m.group(1)
        if "follower" in txt.lower():
            stats["followers"] = num
        if "following" in txt.lower():
            stats["following"] = num
        if "answer" in txt.lower():
            stats["answers"] = num
        if "question" in txt.lower():
            stats["questions"] = num

    if not name:
        return {"_error": "blocked by Cloudflare or JS rendering required"}

    return {
        "name": name,
        "bio": bio,
        "avatar_url": avatar,
        **stats,
    }


def scrape(username: str, m_b: str | None = None) -> dict:
    m_b = m_b or os.environ.get("QUORA_M_B")
    raw_cookie = os.environ.get("QUORA_COOKIE")
    s = new_session()
    s.headers.update(EXTRA_BROWSER_HEADERS)
    url = f"https://www.quora.com/profile/{username}"

    cookie_headers = _cookie_headers(m_b, raw_cookie)
    if cookie_headers:
        s.headers.update(cookie_headers)

    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 403:
        html_pw, pw_error = _fetch_with_playwright(url, m_b, raw_cookie)
        if html_pw and not _cloudflare_block(html_pw):
            data = _parse_profile(html_pw, username)
            if "_error" not in data:
                return ok(
                    SITE,
                    username,
                    {
                        "url": url,
                        "username": username,
                        **data,
                    },
                )
        reason = "403 Cloudflare block. Export QUORA_M_B or QUORA_COOKIE from a logged-in browser session"
        if pw_error:
            reason += f"; {pw_error}"
        else:
            reason += ", or Playwright fallback could not extract profile data."
        return err(SITE, reason)
    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    data = _parse_profile(r.text, username)
    if "_error" in data:
        html_pw, pw_error = _fetch_with_playwright(url, m_b, raw_cookie)
        if html_pw and not _cloudflare_block(html_pw):
            data = _parse_profile(html_pw, username)
            if "_error" not in data:
                return ok(
                    SITE,
                    username,
                    {
                        "url": url,
                        "username": username,
                        **data,
                    },
                )
        reason = data["_error"]
        if pw_error:
            reason = f"{reason}; {pw_error}"
        return err(SITE, reason)

    return ok(
        SITE,
        username,
        {
            "url": url,
            "username": username,
            **data,
        },
    )


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "Elon-Musk-3"
    print(dump(scrape(username)))
