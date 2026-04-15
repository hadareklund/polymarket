"""
doxbin_user_info.py
Best-effort Doxbin profile metadata scraper.

Notes:
  - Doxbin frequently changes domains and is often protected by Cloudflare.
  - This scraper intentionally extracts only compact public metadata.
"""

import re
import sys

from scraper_base import new_session, ok, err, dump

SITE = "doxbin"
BASE_CANDIDATES = [
    "https://doxbin.com",
    "https://doxbin.net",
]


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
    ]
    low = page.lower()
    return any(marker in low for marker in markers)


def scrape(username: str) -> dict:
    s = new_session()

    attempts: list[dict] = []
    for base in BASE_CANDIDATES:
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
                attempts.append(
                    {
                        "url": url,
                        "status": "blocked",
                        "reason": f"HTTP {r.status_code} / Cloudflare challenge",
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
        "no accessible Doxbin profile endpoint found; likely DNS/Cloudflare/domain drift",
    ) | {"attempts": attempts[:10]}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "test"
    print(dump(scrape(target)))
