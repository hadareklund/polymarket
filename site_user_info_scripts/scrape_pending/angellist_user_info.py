"""
angellist_user_info.py
Scrapes a Wellfound (fmr. AngelList) public profile page.

Profile URL: https://wellfound.com/u/{username}

Returns fields:
  name, headline, location, bio, avatar_url,
  skills[], roles[], past_companies[], social_links{},
  followers, following, joined_year
"""

import sys, re, json
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "wellfound"


def scrape(username: str) -> dict:
    url = f"https://wellfound.com/u/{username}"
    s = new_session()

    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code == 403:
        return err(SITE, "blocked (403) — may need session cookies or Playwright")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    # ── Next.js page data (most reliable) ──────────────────────────────────
    next_data_match = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        r.text,
        re.IGNORECASE | re.DOTALL,
    )
    if next_data_match:
        try:
            data = json.loads(next_data_match.group(1))
            user = data.get("props", {}).get("pageProps", {}).get("user") or data.get(
                "props", {}
            ).get("pageProps", {}).get("talent")
            if user:
                roles = [r.get("title", "") for r in (user.get("roles") or [])]
                skills = [s.get("name", "") for s in (user.get("skills") or [])]
                past = [
                    c.get("company", {}).get("name", "")
                    for c in (user.get("pastJobs") or [])
                ]
                return ok(
                    SITE,
                    username,
                    {
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
                    },
                )
        except (json.JSONDecodeError, KeyError):
            pass

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
