"""
pastebin_user_info.py
Collects Pastebin user information with compact, structured output.

Public mode:
  • Reads profile page at https://pastebin.com/u/{username}
  • Extracts profile metadata and visible public paste links when available

Optional account mode (own account only):
  • Uses Pastebin API list endpoint with PASTEBIN_API_KEY, PASTEBIN_PASSWORD,
    and PASTEBIN_USERNAME to include your own paste list.
"""

import os
import re
import sys
import html
from xml.etree import ElementTree

from scraper_base import new_session, ok, err, dump

SITE = "pastebin"
PROFILE_URL = "https://pastebin.com/u/{username}"
API_LOGIN = "https://pastebin.com/api/api_login.php"
API_POST = "https://pastebin.com/api/api_post.php"


def _extract_title(page: str) -> str:
    m = re.search(r"<title>(.*?)</title>", page, re.IGNORECASE | re.DOTALL)
    return html.unescape(m.group(1).strip()) if m else ""


def _extract_meta(page: str, meta_name: str) -> str | None:
    patterns = [
        rf'<meta\s+name=["\']{re.escape(meta_name)}["\']\s+content=["\']([^"\']*)["\']',
        rf'<meta\s+property=["\']{re.escape(meta_name)}["\']\s+content=["\']([^"\']*)["\']',
    ]
    for pat in patterns:
        m = re.search(pat, page, re.IGNORECASE)
        if m:
            return html.unescape(m.group(1).strip())
    return None


def _extract_canonical(page: str) -> str | None:
    m = re.search(
        r'<link\s+rel=["\']canonical["\']\s+href=["\']([^"\']+)["\']',
        page,
        re.IGNORECASE,
    )
    return m.group(1).strip() if m else None


def _extract_public_pastes(page: str) -> list[dict]:
    # Focus on links in the main content area and avoid archive sidebar links that
    # include source=public_pastes.
    items: list[dict] = []
    for m in re.finditer(
        r'<a\s+href=["\']/([A-Za-z0-9]{8})(?:\?[^"\']*)?["\'][^>]*>(.*?)</a>',
        page,
        re.IGNORECASE | re.DOTALL,
    ):
        href_id = m.group(1)
        title = re.sub(r"<[^>]+>", " ", m.group(2))
        title = " ".join(html.unescape(title).split())
        if not title or len(title) < 2:
            continue

        url = f"https://pastebin.com/{href_id}"
        item = {"id": href_id, "title": title, "url": url}
        if item not in items:
            items.append(item)

    return items[:25]


def _extract_display_name(title_text: str) -> str | None:
    # Example: "Pastebin's Pastebin - Pastebin.com"
    m = re.match(r"(.+?)'s\s+Pastebin\s+-\s+Pastebin\.com", title_text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _api_login_and_list(s, username: str) -> tuple[list[dict], str | None]:
    api_key = os.environ.get("PASTEBIN_API_KEY")
    api_user = os.environ.get("PASTEBIN_USERNAME")
    api_password = os.environ.get("PASTEBIN_PASSWORD")

    if not (api_key and api_user and api_password):
        return [], None

    # API list endpoint can only return the authenticated user's own pastes.
    if username.lower() != api_user.lower():
        return [], "PASTEBIN_USERNAME does not match target username; skipped API list"

    lr = s.post(
        API_LOGIN,
        data={
            "api_dev_key": api_key,
            "api_user_name": api_user,
            "api_user_password": api_password,
        },
        timeout=15,
    )
    if lr.status_code != 200 or lr.text.startswith("Bad API request"):
        return [], f"Pastebin API login failed: {lr.text[:140].strip()}"

    user_key = lr.text.strip()
    pr = s.post(
        API_POST,
        data={
            "api_option": "list",
            "api_dev_key": api_key,
            "api_user_key": user_key,
            "api_results_limit": "50",
        },
        timeout=15,
    )

    if pr.status_code != 200:
        return [], f"Pastebin API list failed: HTTP {pr.status_code}"
    if pr.text.startswith("No pastes found"):
        return [], None
    if pr.text.startswith("Bad API request"):
        return [], f"Pastebin API list error: {pr.text[:140].strip()}"

    xml_body = f"<root>{pr.text}</root>"
    try:
        root = ElementTree.fromstring(xml_body)
    except ElementTree.ParseError:
        return [], "Pastebin API list returned non-XML payload"

    items: list[dict] = []
    for paste in root.findall("paste"):
        key = paste.findtext("paste_key")
        if not key:
            continue
        items.append(
            {
                "id": key,
                "title": paste.findtext("paste_title") or "Untitled",
                "date": paste.findtext("paste_date"),
                "size": paste.findtext("paste_size"),
                "private": paste.findtext("paste_private"),
                "format_long": paste.findtext("paste_format_long"),
                "url": f"https://pastebin.com/{key}",
            }
        )

    return items[:50], None


def scrape(username: str) -> dict:
    s = new_session()
    url = PROFILE_URL.format(username=username)

    try:
        r = s.get(url, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 404:
        return err(SITE, "user not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    page = r.text
    title = _extract_title(page)
    if "Not Found" in title:
        return err(SITE, "user not found")

    display_name = _extract_display_name(title)
    public_pastes = _extract_public_pastes(page)

    api_pastes, api_note = _api_login_and_list(s, username)

    data = {
        "url": url,
        "username": username,
        "display_name": display_name,
        "profile_title": title or None,
        "profile_description": _extract_meta(page, "description"),
        "canonical_url": _extract_canonical(page),
        "og_title": _extract_meta(page, "og:title"),
        "public_pastes_count_detected": len(public_pastes),
        "public_pastes": public_pastes,
        "api_pastes_count": len(api_pastes),
        "api_pastes": api_pastes,
        "note": (
            api_note
            or "Pastebin has no public API for global username lookup; data is best-effort from profile HTML and optional own-account API list."
        ),
    }

    return ok(SITE, username, data)


if __name__ == "__main__":
    username = sys.argv[1] if len(sys.argv) > 1 else "pastebin"
    print(dump(scrape(username)))
