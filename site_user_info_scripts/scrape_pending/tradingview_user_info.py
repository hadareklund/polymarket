"""
tradingview_user_info.py
Scrapes a TradingView public profile.

Profile URL: https://www.tradingview.com/u/{username}/

TradingView does not expose a public user REST API — all profile data
is rendered into the page HTML via server-side React hydration.
This script parses that HTML and the embedded JSON state.

Returns fields:
  username, display_name, bio, avatar_url, profile_url,
  followers, following, reputation, joined,
  social_links{}, ideas_count, scripts_count,
  recent_ideas[{title, url, symbol, timeframe, likes, comments, date}],
  recent_scripts[{title, url, likes, copies, date}]
"""

import sys, os, re, json
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "tradingview"


def _parse(html: str, username: str) -> dict:
    if "Page not found" in html:
        return {"_error": "user not found"}

    # Try regex-based extraction first to avoid hard dependency on BeautifulSoup.
    init_match = re.search(r"window\.initData\s*=\s*(\{.+?\});", html, re.DOTALL)
    if init_match:
        try:
            data = json.loads(init_match.group(1))
            user = data.get("user") or data.get("profile") or data.get("userData")
            if user:
                return _extract_from_json(user, username)
        except Exception:
            pass

    next_match = re.search(
        r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    if next_match:
        try:
            data = json.loads(next_match.group(1).strip())
            props = data.get("props", {}).get("pageProps", {})
            user = props.get("profile") or props.get("user")
            if user:
                return _extract_from_json(user, username)
        except Exception:
            pass

    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:
        title_m = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        if title_m and "404" in title_m.group(1):
            return {"_error": "user not found"}
        return {
            "display_name": username,
            "bio": None,
            "avatar_url": None,
            "recent_ideas": [],
            "_note": "partial data without beautifulsoup4",
        }

    soup = BeautifulSoup(html, "lxml")

    if "404" in soup.title.string if soup.title else "":
        return {"_error": "user not found"}

    # TradingView embeds data in window.initData or __NEXT_DATA__
    for tag in soup.find_all("script"):
        text = tag.string or ""

        # Pattern 1: window.initData = {...}
        m = re.search(
            r"window\.initData\s*=\s*(\{.+?\});?\s*(?:var |</script>)", text, re.DOTALL
        )
        if m:
            try:
                data = json.loads(m.group(1))
                user = data.get("user") or data.get("profile") or data.get("userData")
                if user:
                    return _extract_from_json(user, username)
            except Exception:
                pass

        # Pattern 2: __NEXT_DATA__
        if "__NEXT_DATA__" in text or tag.get("id") == "__NEXT_DATA__":
            try:
                data = json.loads(tag.string)
                props = data.get("props", {}).get("pageProps", {})
                user = props.get("profile") or props.get("user")
                if user:
                    return _extract_from_json(user, username)
            except Exception:
                pass

    # Fallback: HTML parsing
    display_name = safe_text(
        soup.select_one("h1[class*='username'], span[class*='displayName']")
    )
    bio = safe_text(soup.select_one("div[class*='bio'], p[class*='bio']"))
    avatar_el = soup.select_one("img[class*='avatar'], img[class*='photo']")
    avatar = avatar_el.get("src") if avatar_el else None

    # Stat blocks — followers / following / reputation
    stats = {}
    for el in soup.select(
        "a[class*='followers'], a[class*='following'], span[class*='reputation']"
    ):
        txt = safe_text(el)
        n = re.search(r"([\d,.]+[KMB]?)", txt)
        if not n:
            continue
        if "follower" in txt.lower():
            stats["followers"] = n.group(1)
        if "following" in txt.lower():
            stats["following"] = n.group(1)
        if "reputation" in txt.lower():
            stats["reputation"] = n.group(1)

    # Ideas
    ideas = []
    for card in soup.select("div[class*='idea-card'], article[class*='idea']"):
        a = card.select_one("a[href*='/p/']")
        if a:
            ideas.append(
                {
                    "title": safe_text(a),
                    "url": "https://www.tradingview.com" + a.get("href", ""),
                    "likes": safe_text(card.select_one("span[class*='likes']")),
                    "date": safe_text(card.select_one("time")),
                }
            )

    return {
        "display_name": display_name or username,
        "bio": bio,
        "avatar_url": avatar,
        "recent_ideas": ideas[:10],
        **stats,
        "_note": "partial data — full data may need JS rendering",
    }


def _extract_from_json(user: dict, username: str) -> dict:
    ideas = []
    for idea in (user.get("ideas") or user.get("publishedIdeas") or [])[:10]:
        ideas.append(
            {
                "title": idea.get("title"),
                "url": idea.get("url") or idea.get("shortUrl"),
                "symbol": idea.get("symbol"),
                "timeframe": idea.get("interval"),
                "likes": idea.get("agreed") or idea.get("likes"),
                "comments": idea.get("commentsCount"),
                "date": idea.get("created") or idea.get("date"),
            }
        )

    scripts = []
    for sc in (user.get("scripts") or [])[:10]:
        scripts.append(
            {
                "title": sc.get("scriptName") or sc.get("title"),
                "url": sc.get("url"),
                "likes": sc.get("likes"),
                "copies": sc.get("copies"),
                "date": sc.get("created"),
            }
        )

    socials = user.get("socialLinks") or {}
    return {
        "display_name": user.get("displayName") or user.get("username"),
        "bio": user.get("description") or user.get("bio"),
        "avatar_url": user.get("avatar") or user.get("profileImageUrl"),
        "followers": user.get("followersCount") or user.get("followers"),
        "following": user.get("followingCount") or user.get("following"),
        "reputation": user.get("reputation"),
        "joined": user.get("registrationDate") or user.get("joined"),
        "ideas_count": user.get("ideasCount") or len(ideas),
        "scripts_count": user.get("scriptsCount") or len(scripts),
        "social_links": {
            "twitter": socials.get("twitter"),
            "website": socials.get("website") or user.get("website"),
            "youtube": socials.get("youtube"),
            "telegram": socials.get("telegram"),
        },
        "recent_ideas": ideas,
        "recent_scripts": scripts,
    }


def scrape(username: str) -> dict:
    s = new_session()
    url = f"https://www.tradingview.com/u/{username}/"

    try:
        r = s.get(url, timeout=20)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    data = _parse(r.text, username)
    if "_error" in data:
        return err(SITE, data["_error"])

    return ok(SITE, username, {"url": url, **data})


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "TradingView"
    print(dump(scrape(username)))
