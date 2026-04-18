"""
crunchbase_full_name_search.py
Search Crunchbase people by full name and scrape public profile metadata.

No API key is used.

Usage:
  python crunchbase_full_name_search.py "Mark Zuckerberg"
  python crunchbase_full_name_search.py "Mark" --max-results 8
"""

from __future__ import annotations

import argparse
import html
import importlib
import json
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse
import requests

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def new_session() -> requests.Session:
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def get_beautifulsoup():
    try:
        return importlib.import_module("bs4").BeautifulSoup
    except Exception:
        return None


def safe_text(el) -> str:
    return el.get_text(strip=True) if el else ""


def dump(obj: dict) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False)


def err(site: str, reason: str) -> dict:
    return {"site": site, "status": "error", "reason": reason}


def ok(site: str, username: str, data: dict) -> dict:
    return {"site": site, "status": "ok", "username": username, **data}


SITE = "crunchbase_full_name_search"
BRAVE_SEARCH_URL = "https://search.brave.com/search"
DUCKDUCKGO_SEARCH_URL = "https://duckduckgo.com/html/"


def _normalize_profile_url(raw_url: str) -> str | None:
    """Extract a clean Crunchbase person URL from a search-result link."""
    if not raw_url:
        return None

    candidate = html.unescape(raw_url).strip()
    if candidate.startswith("//"):
        candidate = f"https:{candidate}"

    parsed = urlparse(candidate)

    # DuckDuckGo wraps external links as /l/?uddg=<encoded_target>
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        qs = parse_qs(parsed.query)
        target = qs.get("uddg", [""])[0]
        if target:
            candidate = unquote(target)
            parsed = urlparse(candidate)

    netloc = parsed.netloc.lower()
    path = re.sub(r"/+", "/", parsed.path or "")
    parts = [p for p in path.split("/") if p]

    if "crunchbase.com" not in netloc or len(parts) < 2 or parts[0] != "person":
        return None

    slug = parts[1]
    return f"https://www.crunchbase.com/person/{slug}"


def _extract_profile_links(search_html: str, max_results: int) -> list[str]:
    """Extract unique Crunchbase profile links from search result HTML."""
    links: list[str] = []
    seen: set[str] = set()

    # Regex fallback keeps this script dependency-light.
    for href in re.findall(
        r'href\s*=\s*["\']([^"\']+)["\']', search_html, flags=re.IGNORECASE
    ):
        url = _normalize_profile_url(href)
        if not url or url in seen:
            continue
        seen.add(url)
        links.append(url)
        if len(links) >= max_results:
            break

    return links


def _search_brave(query: str, max_results: int) -> list[str]:
    s = new_session()
    r = s.get(
        BRAVE_SEARCH_URL,
        params={"q": query, "source": "web"},
        timeout=20,
    )
    if r.status_code != 200:
        return []
    return _extract_profile_links(r.text, max_results=max_results)


def _search_duckduckgo(query: str, max_results: int) -> list[str]:
    s = new_session()
    r = s.get(DUCKDUCKGO_SEARCH_URL, params={"q": query}, timeout=20)
    if r.status_code != 200:
        return []
    return _extract_profile_links(r.text, max_results=max_results)


def _slug_relevance(slug: str, full_name: str) -> int:
    slug_norm = re.sub(r"[^a-z0-9-]", "", (slug or "").lower())
    tokens = [
        re.sub(r"[^a-z0-9]", "", token.lower())
        for token in full_name.split()
        if token.strip()
    ]
    tokens = [t for t in tokens if len(t) >= 2]
    return sum(1 for token in tokens if token in slug_norm)


def _meta_content(html_text: str, attr: str, key: str) -> str | None:
    pattern = (
        rf'<meta[^>]*{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']+)["\']'
    )
    m = re.search(pattern, html_text, flags=re.IGNORECASE)
    if m:
        return html.unescape(m.group(1)).strip()

    reverse_pattern = (
        rf'<meta[^>]*content=["\']([^"\']+)["\'][^>]*{attr}=["\']{re.escape(key)}["\']'
    )
    m = re.search(reverse_pattern, html_text, flags=re.IGNORECASE)
    if m:
        return html.unescape(m.group(1)).strip()

    return None


def _parse_json_ld(html_text: str) -> dict:
    person = {}
    blocks = re.findall(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html_text,
        flags=re.IGNORECASE | re.DOTALL,
    )

    def walk(node):
        if isinstance(node, dict):
            node_type = node.get("@type")
            is_person = node_type == "Person" or (
                isinstance(node_type, list) and "Person" in node_type
            )
            if is_person and not person:
                person.update(node)
                return
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for raw in blocks:
        raw = raw.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        walk(payload)
        if person:
            break

    if not person:
        return {}

    works_for = person.get("worksFor")
    if isinstance(works_for, dict):
        works_for = works_for.get("name")
    elif isinstance(works_for, list):
        names = []
        for w in works_for:
            if isinstance(w, dict):
                n = w.get("name")
                if n:
                    names.append(n)
        works_for = names or None

    return {
        "name": person.get("name"),
        "description": person.get("description"),
        "job_title": person.get("jobTitle"),
        "image": person.get("image"),
        "same_as": person.get("sameAs"),
        "works_for": works_for,
    }


def _fallback_profile_parse(profile_html: str) -> dict:
    title = _meta_content(profile_html, "property", "og:title") or _meta_content(
        profile_html, "name", "title"
    )
    description = _meta_content(
        profile_html, "property", "og:description"
    ) or _meta_content(profile_html, "name", "description")
    image = _meta_content(profile_html, "property", "og:image")

    BeautifulSoup = get_beautifulsoup()
    if BeautifulSoup:
        soup = BeautifulSoup(profile_html, "lxml")
        if not title:
            title = safe_text(soup.find("title"))

    return {
        "name": title,
        "description": description,
        "job_title": None,
        "image": image,
        "same_as": None,
        "works_for": None,
    }


def scrape_profile(profile_url: str) -> dict:
    s = new_session()

    try:
        r = s.get(profile_url, timeout=20)
    except Exception as exc:
        return {"url": profile_url, "status": "error", "reason": str(exc)}

    if r.status_code != 200:
        return {
            "url": profile_url,
            "status": "error",
            "reason": f"HTTP {r.status_code}",
        }

    parsed = _parse_json_ld(r.text)
    if not parsed:
        parsed = _fallback_profile_parse(r.text)

    slug = profile_url.rstrip("/").split("/")[-1]
    return {
        "url": profile_url,
        "slug": slug,
        "status": "ok",
        **parsed,
    }


def scrape(full_name: str, max_results: int = 5) -> dict:
    full_name = (full_name or "").strip()
    if not full_name:
        return err(SITE, "full_name is required")

    query_variants = [
        f'site:crunchbase.com/person "{full_name}"',
        f"site:crunchbase.com/person {full_name}",
        f'"{full_name}" site:crunchbase.com/person',
    ]

    search_attempts = []
    links: list[str] = []
    search_engine = ""
    selected_query = ""

    for query in query_variants:
        for engine_name, search_fn in (
            ("brave", _search_brave),
            ("duckduckgo", _search_duckduckgo),
        ):
            try:
                found = search_fn(query, max_results=max_results * 4)
            except Exception as exc:
                search_attempts.append(
                    {
                        "engine": engine_name,
                        "query": query,
                        "error": str(exc),
                    }
                )
                continue

            search_attempts.append(
                {
                    "engine": engine_name,
                    "query": query,
                    "found_links": len(found),
                }
            )
            if found:
                links = found
                search_engine = engine_name
                selected_query = query
                break
        if links:
            break

    if not links:
        return err(
            SITE,
            "No Crunchbase profile links found in search results. Try a fuller name.",
        )

    ranked = []
    for idx, url in enumerate(links):
        slug = url.rstrip("/").split("/")[-1]
        ranked.append((url, _slug_relevance(slug, full_name), idx))
    ranked.sort(key=lambda item: (-item[1], item[2]))
    selected_links = [url for url, _, _ in ranked[:max_results]]

    results = [scrape_profile(url) for url in selected_links]

    for item in results:
        slug = item.get("slug") or item.get("url", "").rstrip("/").split("/")[-1]
        item["slug_query_relevance"] = _slug_relevance(slug, full_name)
        if item.get("status") != "ok":
            if item.get("reason") == "HTTP 403":
                item["note"] = (
                    "Crunchbase blocked direct profile scraping (403). "
                    "Name-based search discovery still worked without API keys."
                )
            continue
        candidate_name = (item.get("name") or "").lower()
        item["name_query_match"] = full_name.lower() in candidate_name

    return ok(
        SITE,
        full_name,
        {
            "query": full_name,
            "search_query": selected_query,
            "search_engine": search_engine,
            "search_attempts": search_attempts,
            "results_count": len(results),
            "results": results,
            "note": "Public web scraping only. No API key used.",
        },
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search Crunchbase by full name and scrape public profile pages"
    )
    parser.add_argument(
        "full_name", nargs="+", help='Full name, e.g. "Mark Zuckerberg"'
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=5,
        help="Maximum profiles to return (default: 5)",
    )
    args = parser.parse_args()

    full_name = " ".join(args.full_name).strip()
    max_results = max(1, min(args.max_results, 20))
    print(dump(scrape(full_name, max_results=max_results)))


if __name__ == "__main__":
    main()
