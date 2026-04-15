"""
researchgate_user_info.py
Scrapes a ResearchGate public profile.

ResearchGate is behind Cloudflare (error 1020) for cold requests.
Works best with a real browser session cookie.

  MODE 1 — Session cookie (recommended):
    export RG_COOKIE="__cf_bm=...; cf_clearance=...; _ga=..."
    Copy all cookies from a logged-in browser session as a single string.

  MODE 2 — Cold request (often blocked):
    Returns partial data if Cloudflare doesn't intercept.

Profile URL: https://www.researchgate.net/profile/{First-Last}
  or:        https://www.researchgate.net/scientific-contributions/{slug}

Returns fields:
  name, username (slug), institution, department, position,
  field_of_study[], bio, avatar_url, profile_url,
  rg_score, citations, reads, research_interest,
  publications_count, questions_count, followers, following,
  publications[{title, date, type, doi, reads, citations, url}]
"""

import sys, os, re, json
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "researchgate"


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

    if r.status_code == 403 or "error code: 1020" in r.text:
        return err(
            SITE,
            "Cloudflare block. Set RG_COOKIE with cookies from a real browser session.",
        )
    if r.status_code == 404:
        return err(SITE, "profile not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    data = _parse(r.text, slug)
    if "_error" in data:
        return err(SITE, data["_error"])

    return ok(SITE, slug, {"url": url, **data})


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "Yoshua-Bengio"
    print(dump(scrape(slug)))
