"""
bitcointalk_user_info.py
Scrapes a Bitcointalk public profile.

Supports lookup by:
  • numeric user ID  (e.g. "3")
    • username string  (resolves to ID via profile lookup first)

Profile URL: https://bitcointalk.org/index.php?action=profile;u={uid}

Returns fields:
  user_id, username, position, date_registered, last_active,
  email (if public), signature, posts, merit, activity,
  trust_score, website, bitcoin_address, avatar_url, local_time
"""

import html as html_lib
import sys, re
from scraper_base import new_session, safe_text, ok, err, dump, get_beautifulsoup

SITE = "bitcointalk"
BASE = "https://bitcointalk.org/index.php"

# ── helpers ────────────────────────────────────────────────────────────────


def _resolve_uid(s, username: str) -> str | None:
    """Try to get numeric UID from a username string."""
    # Most reliable path: Bitcointalk accepts username-based profile URLs.
    try:
        r = s.get(
            BASE,
            params={"action": "profile", "user": username},
            timeout=15,
        )
        m = re.search(r"action=profile;u=(\d+)", r.text, re.IGNORECASE)
        if m:
            return m.group(1)
    except Exception:
        pass

    # Legacy fallback: member search page (may be guest-restricted/captcha-gated).
    try:
        r = s.get(
            BASE,
            params={
                "action": "search2",
                "search": username,
                "searchtype": "1",  # member search
            },
            timeout=15,
        )
        m = re.search(
            rf'action=profile;u=(\d+)[^"]*"[^>]*>{re.escape(username)}<',
            r.text,
            re.IGNORECASE,
        )
        if m:
            return m.group(1)
        # broader fallback — first hit
        m = re.search(r"action=profile;u=(\d+)", r.text)
        return m.group(1) if m else None
    except Exception:
        return None


def _parse_profile(uid: str, html: str) -> dict:
    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:

        def strip_tags(s: str) -> str:
            return " ".join(re.sub(r"<[^>]+>", " ", html_lib.unescape(s)).split())

        def td_after_regex(label: str) -> str:
            m = re.search(
                rf"{re.escape(label)}\s*:\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>",
                html,
                re.IGNORECASE | re.DOTALL,
            )
            return strip_tags(m.group(1)) if m else ""

        name_m = re.search(
            r"Name\s*:\s*</b>\s*</td>\s*<td[^>]*>(.*?)</td>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        sig_m = re.search(
            r"<div[^>]*class=[\"']signature[\"'][^>]*>(.*?)</div>",
            html,
            re.IGNORECASE | re.DOTALL,
        )
        avatar_m = re.search(
            r"<img[^>]+src=[\"']([^\"']+)[\"'][^>]*>", html, re.IGNORECASE
        )
        merit_m = re.search(r"Merit:\s*</b>\s*([\d,]+)", html)
        activity_m = re.search(r"Activity:\s*</b>\s*([\d,]+)", html)
        posts_m = re.search(r"Posts:\s*</b>\s*([\d,]+)", html)
        trust_m = re.search(r"Trust:\s*</b>\s*([-+\d]+)", html)

        return {
            "url": f"{BASE}?action=profile;u={uid}",
            "user_id": uid,
            "username": strip_tags(name_m.group(1)) if name_m else "",
            "position": td_after_regex("Position"),
            "date_registered": td_after_regex("Date Registered"),
            "last_active": td_after_regex("Last Active"),
            "local_time": td_after_regex("Local Time"),
            "posts": posts_m.group(1).replace(",", "") if posts_m else None,
            "merit": merit_m.group(1).replace(",", "") if merit_m else None,
            "activity": activity_m.group(1).replace(",", "") if activity_m else None,
            "trust_score": trust_m.group(1) if trust_m else None,
            "email": td_after_regex("Email"),
            "website": td_after_regex("Website") or td_after_regex("Personal text"),
            "bitcoin_address": td_after_regex("Bitcoin address"),
            "signature": strip_tags(sig_m.group(1)) if sig_m else "",
            "avatar_url": avatar_m.group(1) if avatar_m else None,
        }

    soup = BeautifulSoup(html, "lxml")

    def td_after(label: str) -> str:
        """Find <td> whose text matches label, return the next sibling td."""
        for td in soup.find_all("td"):
            if label.lower() in safe_text(td).lower():
                nxt = td.find_next_sibling("td")
                if nxt:
                    return safe_text(nxt)
        return ""

    username = safe_text(
        soup.select_one("td.windowbg2 b") or soup.find("b", string=re.compile(r".+"))
    )
    # Stat rows are in a definition-list style table
    name_el = soup.select_one("td[id='profileinfo'] > table td b")
    if name_el:
        username = safe_text(name_el)

    avatar_el = soup.select_one("img[class*='avatar'], td.windowbg img")
    avatar = avatar_el["src"] if avatar_el else None

    # Pull stats from the profile table rows
    def stat(label):
        return td_after(label)

    # Merit / activity are in a separate stats block
    merit_m = re.search(r"Merit:\s*</b>\s*([\d,]+)", html)
    activity_m = re.search(r"Activity:\s*</b>\s*([\d,]+)", html)
    posts_m = re.search(r"Posts:\s*</b>\s*([\d,]+)", html)
    trust_m = re.search(r"Trust:\s*</b>\s*([-+\d]+)", html)

    return {
        "url": f"{BASE}?action=profile;u={uid}",
        "user_id": uid,
        "username": stat("Name") or username,
        "position": stat("Position"),
        "date_registered": stat("Date Registered"),
        "last_active": stat("Last Active"),
        "local_time": stat("Local Time"),
        "posts": posts_m.group(1).replace(",", "") if posts_m else None,
        "merit": merit_m.group(1).replace(",", "") if merit_m else None,
        "activity": activity_m.group(1).replace(",", "") if activity_m else None,
        "trust_score": trust_m.group(1) if trust_m else None,
        "email": stat("Email"),
        "website": stat("Website") or stat("Personal text"),
        "bitcoin_address": stat("Bitcoin address"),
        "signature": safe_text(soup.select_one("div.signature")),
        "avatar_url": avatar,
    }


# ── main ───────────────────────────────────────────────────────────────────


def scrape(username_or_id: str) -> dict:
    s = new_session()

    # Determine UID
    uid = username_or_id if username_or_id.isdigit() else None
    if uid is None:
        uid = _resolve_uid(s, username_or_id)
        if uid is None:
            return err(SITE, f"could not resolve username '{username_or_id}' to a UID")

    try:
        r = s.get(BASE, params={"action": "profile", "u": uid}, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")
    if "An Error Has Occurred" in r.text or "The user whose profile" in r.text:
        return err(SITE, "profile not found or hidden")

    parsed = _parse_profile(uid, r.text)
    return ok(SITE, parsed.get("username") or username_or_id, parsed)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "3"  # Satoshi is uid 3
    print(dump(scrape(target)))
