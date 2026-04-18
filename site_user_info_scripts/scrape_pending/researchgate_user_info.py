"""
researchgate_user_info.py
Scrapes a ResearchGate public profile.

ResearchGate is behind Cloudflare (error 1020) for cold requests.
This scraper now tries multiple fetch modes automatically.

    MODE 1 — Plain requests (default):
        Fast path; works when Cloudflare does not block.

    MODE 2 — Browser fallback (automatic):
        Uses Playwright headless Chromium if requests are blocked or parsing fails.

    MODE 3 — Session cookie (recommended if still blocked):
    export RG_COOKIE="__cf_bm=...; cf_clearance=...; _ga=..."
    Copy all cookies from a logged-in browser session as a single string.

Profile URL: https://www.researchgate.net/profile/{First-Last}
  or:        https://www.researchgate.net/scientific-contributions/{slug}

Returns fields:
  name, username (slug), institution, department, position,
  field_of_study[], bio, avatar_url, profile_url,
  rg_score, citations, reads, research_interest,
  publications_count, questions_count, followers, following,
  publications[{title, date, type, doi, reads, citations, url}]
"""

import sys, os, re, json, importlib
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "researchgate"


def _is_cloudflare_block(status_code: int | None, html: str) -> bool:
    low = (html or "").lower()
    return bool(
        status_code in {403, 429}
        or "error code: 1020" in low
        or "cf-error-details" in low
        or "cloudflare" in low
        or "cf-challenge" in low
        or "verify you are human" in low
    )


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
                "domain": ".researchgate.net",
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
            "Playwright not installed. Run: python3 -m pip install playwright && python3 -m playwright install chromium",
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

            if cookie_header:
                parsed = _parse_cookie_header(cookie_header)
                if parsed:
                    context.add_cookies(parsed)

            page = context.new_page()
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(2500)
            html = page.content()
            status = resp.status if resp else None
            context.close()
            browser.close()
            return html, status, None
    except Exception as e:
        return None, None, f"Playwright fetch failed: {e}"


def _parse(html: str, slug: str) -> dict:
    if "cf-error-details" in html or "error code: 1020" in html:
        return {"_error": "Cloudflare block (1020) — set RG_COOKIE env var"}

    # JSON-LD structured data
    ld = {}
    ld_match = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if ld_match:
        try:
            ld = json.loads(ld_match.group(1).strip())
        except Exception:
            pass

    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:
        title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        followers_m = re.search(r'"followerCount"\s*:\s*(\d+)', html)
        following_m = re.search(r'"followingCount"\s*:\s*(\d+)', html)
        return {
            "name": ld.get("name") or (title_m.group(1).strip() if title_m else None),
            "position": None,
            "institution": (
                ld.get("affiliation", {}).get("name")
                if isinstance(ld.get("affiliation"), dict)
                else None
            ),
            "department": None,
            "avatar_url": ld.get("image"),
            "rg_score": None,
            "citations": None,
            "reads": None,
            "research_interest": None,
            "followers": followers_m.group(1) if followers_m else None,
            "following": following_m.group(1) if following_m else None,
            "publications_count": 0,
            "publications": [],
            "_note": "partial data without beautifulsoup4",
        }

    soup = BeautifulSoup(html, "lxml")

    name = (
        ld.get("name")
        or safe_text(soup.select_one("h1[class*='nova-legacy-e-text']"))
        or safe_text(soup.select_one("h1"))
    )
    institution = (
        ld.get("affiliation", {}).get("name")
        or safe_text(soup.select_one("a[class*='institution']"))
        or safe_text(soup.select_one("div[class*='institution-link']"))
    )
    position = safe_text(
        soup.select_one("span[class*='position'], div[class*='position']")
    )
    department = safe_text(soup.select_one("span[class*='department']"))
    avatar_el = soup.select_one("img[class*='avatar'], img[class*='profile-picture']")
    avatar = avatar_el.get("src") if avatar_el else ld.get("image")

    # RG Score, Citations, Reads
    def stat_by_label(label: str) -> str:
        for el in soup.select("div[class*='nova'], section[class*='nova']"):
            t = safe_text(el)
            if label.lower() in t.lower():
                m = re.search(r"([\d,.]+)", t)
                if m:
                    return m.group(1).replace(",", "")
        return ""

    rg_score = stat_by_label("RG Score") or stat_by_label("rgscore")
    citations = stat_by_label("Citations")
    reads = stat_by_label("Reads")
    ri = stat_by_label("Research Interest")

    # Follower / following counts
    followers_m = re.search(r'"followerCount"\s*:\s*(\d+)', html)
    following_m = re.search(r'"followingCount"\s*:\s*(\d+)', html)

    # Publications list
    pubs = []
    for card in soup.select("div[class*='publication-item'], li[class*='publication']"):
        title_el = card.select_one("a[class*='title'], h3 a, h2 a")
        if not title_el:
            continue
        doi_m = re.search(r"10\.\d{4,}/\S+", card.get_text())
        pubs.append(
            {
                "title": safe_text(title_el),
                "url": title_el.get("href"),
                "type": safe_text(card.select_one("span[class*='type']")),
                "date": safe_text(card.select_one("span[class*='date'], time")),
                "doi": doi_m.group(0) if doi_m else None,
                "reads": safe_text(card.select_one("span[class*='reads']")),
                "citations": safe_text(card.select_one("span[class*='citation']")),
            }
        )

    if not name:
        return {"_error": "could not parse — JS rendering may be required"}

    return {
        "name": name,
        "position": position,
        "institution": institution,
        "department": department,
        "avatar_url": avatar,
        "rg_score": rg_score or None,
        "citations": citations or None,
        "reads": reads or None,
        "research_interest": ri or None,
        "followers": followers_m.group(1) if followers_m else None,
        "following": following_m.group(1) if following_m else None,
        "publications_count": len(pubs),
        "publications": pubs[:20],
    }


def scrape(slug: str, cookie: str | None = None) -> dict:
    """
    slug: the profile slug, e.g. "Jane-Doe-3" from
          https://www.researchgate.net/profile/Jane-Doe-3
    """
    cookie = cookie or os.environ.get("RG_COOKIE")
    s = new_session()
    url = f"https://www.researchgate.net/profile/{slug}"

    if cookie:
        s.headers.update({"Cookie": cookie})

    try:
        r = s.get(url, timeout=20)
    except Exception as e:
        return err(SITE, str(e))

    if _is_cloudflare_block(r.status_code, r.text):
        html_pw, pw_status, pw_error = _fetch_with_playwright(url, cookie)
        if html_pw and not _is_cloudflare_block(pw_status, html_pw):
            data = _parse(html_pw, slug)
            if "_error" in data:
                return err(SITE, data["_error"])
            return ok(SITE, slug, {"url": url, "fetch_mode": "playwright", **data})

        reason = (
            "Cloudflare block after requests + browser fallback. "
            "Set RG_COOKIE with cookies from a real browser session."
        )
        if pw_error:
            reason = f"{reason} {pw_error}"
        return err(SITE, reason)

    if r.status_code == 404:
        return err(SITE, "profile not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    data = _parse(r.text, slug)
    if "_error" in data:
        # If static HTML parse fails due JS/anti-bot behavior, try browser rendering.
        if "js rendering" in data["_error"].lower() or "cloudflare" in data[
            "_error"
        ].lower():
            html_pw, pw_status, pw_error = _fetch_with_playwright(url, cookie)
            if html_pw and not _is_cloudflare_block(pw_status, html_pw):
                data_pw = _parse(html_pw, slug)
                if "_error" not in data_pw:
                    return ok(
                        SITE,
                        slug,
                        {"url": url, "fetch_mode": "playwright", **data_pw},
                    )
            if pw_error:
                return err(SITE, f"{data['_error']}. {pw_error}")
        return err(SITE, data["_error"])

    return ok(SITE, slug, {"url": url, "fetch_mode": "requests", **data})


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "Yoshua-Bengio"
    print(dump(scrape(slug)))
