"""
linkedin_user_info.py
Scrapes a LinkedIn public profile page.

LinkedIn aggressively blocks headless requests (HTTP 999 / 302 to authwall).
This script works in two modes:

  MODE 1 — Cookie auth (recommended):
    Export your li_at cookie from a logged-in browser session.
    export LINKEDIN_LI_AT=your_li_at_cookie_value
    This gives access to the full Voyager internal API.

  MODE 2 — Public HTML scrape (limited):
    No cookie needed but returns far fewer fields and may hit the authwall.

Profile URL: https://www.linkedin.com/in/{username}

Returns fields (cookie mode):
  name, headline, location, summary, industry,
  experience[], education[], skills[], certifications[],
  languages[], connections, followers, profile_pic_url,
  background_pic_url, public_id, urn
"""

import sys, os, re, json
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

SITE = "linkedin"
VOYAGER = "https://www.linkedin.com/voyager/api"


def _cookie_headers(li_at: str) -> dict:
    return {
        "Cookie": f"li_at={li_at}; JSESSIONID=ajax:0000000000000000",
        "Csrf-Token": "ajax:0000000000000000",
        "X-Li-Lang": "en_US",
        "X-Restli-Protocol-Version": "2.0.0",
        "Accept": "application/vnd.linkedin.normalized+json+2.1",
    }


def _voyager_profile(s, username: str) -> dict:
    """Use the internal Voyager API (requires li_at cookie)."""
    url = f"{VOYAGER}/identity/dash/profiles"
    r = s.get(
        url,
        params={
            "q": "memberIdentity",
            "memberIdentity": username,
            "decorationId": "com.linkedin.voyager.dash.deco.identity.profile.FullProfileWithEntities-93",
        },
        timeout=15,
    )

    if r.status_code == 401:
        return {"_error": "auth failed — li_at cookie may be expired"}
    if r.status_code != 200:
        return {"_error": f"HTTP {r.status_code}"}

    try:
        data = r.json()
    except Exception:
        return {"_error": "non-JSON response"}

    # Voyager wraps everything in 'included' array
    elements = data.get("elements") or []
    if not elements:
        included = data.get("included", [])
        profile = next(
            (x for x in included if x.get("$type", "").endswith("Profile")), {}
        )
    else:
        profile = elements[0] if elements else {}

    if not profile:
        return {"_error": "profile object not found in response"}

    # Parse experience
    experience = []
    for item in data.get("included", []):
        t = item.get("$type", "")
        if "Position" in t:
            experience.append(
                {
                    "title": item.get("title"),
                    "company": (
                        item.get("companyName") or item.get("company", {}).get("name")
                    ),
                    "start": item.get("timePeriod", {}).get("startDate"),
                    "end": item.get("timePeriod", {}).get("endDate"),
                    "location": item.get("locationName"),
                    "description": item.get("description"),
                }
            )

    # Parse education
    education = []
    for item in data.get("included", []):
        if "Education" in item.get("$type", ""):
            education.append(
                {
                    "school": item.get("schoolName"),
                    "degree": item.get("degreeName"),
                    "field": item.get("fieldOfStudy"),
                    "start": item.get("timePeriod", {}).get("startDate"),
                    "end": item.get("timePeriod", {}).get("endDate"),
                }
            )

    # Parse skills
    skills = []
    for item in data.get("included", []):
        if "Skill" in item.get("$type", ""):
            skills.append(item.get("name"))

    pic = (
        profile.get("profilePicture", {})
        .get("displayImageReferenceResolutionResult", {})
        .get("vectorImage", {})
        .get("artifacts", [{}])[-1]
        .get("fileIdentifyingUrlPathSegment")
    )

    return {
        "name": profile.get("firstName", "") + " " + profile.get("lastName", ""),
        "headline": profile.get("headline"),
        "location": profile.get("locationName"),
        "summary": profile.get("summary"),
        "industry": profile.get("industryName"),
        "connections": profile.get("connections", {}).get("paging", {}).get("total"),
        "followers": profile.get("followersCount"),
        "urn": profile.get("entityUrn"),
        "profile_pic_url": pic,
        "experience": experience[:10],
        "education": education[:5],
        "skills": [s for s in skills if s][:20],
    }


def _public_html(s, username: str) -> dict:
    """Fallback: parse the public-facing HTML (very limited)."""
    r = s.get(f"https://www.linkedin.com/in/{username}/", timeout=15)
    if r.status_code in (999, 302, 403, 429):
        return {"_error": f"blocked (HTTP {r.status_code}) — use li_at cookie"}
    if r.status_code != 200:
        return {"_error": f"HTTP {r.status_code}"}

    low = r.text.lower()
    if (
        "linkedin respects your privacy" in low
        or "sign in to view" in low
        or "checkpoint/challenge" in low
        or "authwall" in low
    ):
        return {"_error": "authwall/privacy page detected — use li_at cookie"}

    ld_match = re.search(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        r.text,
        re.IGNORECASE | re.DOTALL,
    )
    if ld_match:
        try:
            d = json.loads(ld_match.group(1).strip())
            parsed = {
                "name": d.get("name"),
                "headline": d.get("description") or d.get("jobTitle"),
                "location": d.get("address", {}).get("addressLocality"),
                "url": d.get("url"),
                "image": d.get("image"),
                "alumni_of": [a.get("name") for a in d.get("alumniOf", [])],
                "works_for": [w.get("name") for w in d.get("worksFor", [])],
            }
            if parsed.get("name") or parsed.get("headline") or parsed.get("url"):
                return parsed
        except Exception:
            pass

    BeautifulSoup = get_beautifulsoup()
    if not BeautifulSoup:
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", r.text, re.IGNORECASE | re.DOTALL)
        h2 = re.search(r"<h2[^>]*>(.*?)</h2>", r.text, re.IGNORECASE | re.DOTALL)
        name = re.sub(r"<[^>]+>", " ", h1.group(1)).strip() if h1 else None
        headline = re.sub(r"<[^>]+>", " ", h2.group(1)).strip() if h2 else None
        if name or headline:
            return {
                "name": name,
                "headline": headline,
                "_note": "partial data without beautifulsoup4",
            }
        return {
            "_error": "limited parse failed; install beautifulsoup4 for richer fallback"
        }

    soup = BeautifulSoup(r.text, "lxml")

    # LinkedIn embeds JSON-LD
    ld = soup.find("script", type="application/ld+json")
    if ld:
        try:
            d = json.loads(ld.string)
            parsed = {
                "name": d.get("name"),
                "headline": d.get("description") or d.get("jobTitle"),
                "location": d.get("address", {}).get("addressLocality"),
                "url": d.get("url"),
                "image": d.get("image"),
                "alumni_of": [a.get("name") for a in d.get("alumniOf", [])],
                "works_for": [w.get("name") for w in d.get("worksFor", [])],
            }
            if parsed.get("name") or parsed.get("headline") or parsed.get("url"):
                return parsed
        except Exception:
            pass

    return {
        "name": safe_text(soup.select_one("h1")),
        "headline": safe_text(soup.select_one("h2")),
        "_note": "partial data — consider using li_at cookie for full profile",
    }


def scrape(username: str, li_at: str | None = None) -> dict:
    if load_env_file:
        load_env_file(start_dir=SCRIPT_DIR)

    li_at = li_at or os.environ.get("LINKEDIN_LI_AT")
    s = new_session()
    url = f"https://www.linkedin.com/in/{username}/"

    if li_at:
        s.headers.update(_cookie_headers(li_at))
        data = _voyager_profile(s, username)
        if "_error" in data:
            return err(SITE, data["_error"])
    else:
        data = _public_html(s, username)
        if "_error" in data:
            return err(SITE, data["_error"])

    payload = dict(data)
    if not payload.get("url"):
        payload["url"] = url
    return ok(SITE, username, payload)


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "williamhgates"
    print(dump(scrape(username)))
