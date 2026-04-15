"""
quora_user_info.py
Scrapes a Quora public profile.

Quora returns 403 to cold requests (Cloudflare + bot detection).
Works in two modes:

  MODE 1 — Session cookie (recommended):
    Export your m-b cookie from a logged-in Quora browser session.
    export QUORA_M_B=your_m-b_cookie_value
    Returns full profile including follower counts, answer count, etc.

  MODE 2 — Public HTML (cold):
    Often blocked by Cloudflare. Returns partial data if it gets through.

Profile URL: https://www.quora.com/profile/{username}

Returns fields:
  name, username, bio, profile_url, avatar_url,
  followers, following, answers, questions, posts,
  knows_about[], credentials[], social_links{}
"""

import sys, os, re, json
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "quora"


def _cookie_headers(m_b: str) -> dict:
    return {
        "Cookie": f"m-b={m_b}",
        "Referer": "https://www.quora.com/",
    }


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
    s = new_session()
    url = f"https://www.quora.com/profile/{username}"

    if m_b:
        s.headers.update(_cookie_headers(m_b))

    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 403:
        return err(
            SITE,
            "403 Cloudflare block. Export QUORA_M_B cookie from a logged-in "
            "browser session, or use a Playwright-based scraper.",
        )
    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    data = _parse_profile(r.text, username)
    if "_error" in data:
        return err(SITE, data["_error"])

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
