#!/usr/bin/env python3
"""
Batch LinkedIn lookup using name/company/location data from the main pipeline.

Reads results/<slug>/linkedin_queries.json (generated automatically by run.py)
and for each entry searches for a matching LinkedIn profile, then writes the
result back into the user's results/<slug>/<username>.json.

Query strategy:
  - High confidence + company:  "Logan Johnson" "Square" site:linkedin.com/in/
  - High confidence only:       "Logan Johnson" site:linkedin.com/in/
  - Low confidence + company:   "Richard W" "Google" site:linkedin.com/in/
  - Low confidence, no company: skipped (already excluded from the queries file)
  - Location added when name is common (no company present):
                                "Logan Johnson" "New York" site:linkedin.com/in/

Engine selection (--engine):
  brave  — Brave Search API, key-based auth, immune to IP blocks. Default.
             5,000 free queries/month. Requires BRAVE_API_KEY in env or .env.
  google — Google Custom Search API, 100 free queries/day.
             Requires GOOGLE_API_KEY + GOOGLE_CSE_ID in env or .env.
  bing   — HTTP request, no browser, 5-10 s delay. IP-blocked on datacenter ranges.
  ddg    — Playwright + stealth, 15-25 s delay. Gets IP-blocked under heavy load.

Parallelism: brave/google default to --workers 10 (no delay). bing/ddg default
to --workers 1 (serial, with delays to avoid IP blocks).

Checkpoint/resume: re-run the same command to pick up where you left off.

Usage:
    python3 linkedin_batch.py results/<slug>_analysis/linkedin_queries.json
    python3 linkedin_batch.py results/<slug>_analysis/linkedin_queries.json --workers 20
    python3 linkedin_batch.py results/<slug>_analysis/linkedin_queries.json --engine bing
    python3 linkedin_batch.py results/<slug>_analysis/linkedin_queries.json --engine google
    python3 linkedin_batch.py results/<slug>_analysis/linkedin_queries.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import os
import requests
from urllib.parse import quote_plus, unquote, urlparse

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import brave_usage

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BRAVE_URL      = "https://api.search.brave.com/res/v1/web/search"
BING_URL       = "https://www.bing.com/search"
GOOGLE_CSE_URL = "https://www.googleapis.com/customsearch/v1"
DDG_HTML_URL   = "https://html.duckduckgo.com/html/"

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_linkedin_profile_url(url: str) -> bool:
    p = urlparse(url)
    return "linkedin.com" in p.netloc and p.path.startswith("/in/") and len(p.path.strip("/").split("/")) >= 2

def _strip_tags(s: str) -> str:
    return re.sub(r"<[^>]+>", " ", s)

def _clean(s: str, maxlen: int = 280) -> str:
    s = re.sub(r"&#?\w+;", " ", s)
    return re.sub(r"\s+", " ", s).strip()[:maxlen]

def _load_env_key(name: str) -> str:
    val = os.environ.get(name, "")
    if not val:
        env = SCRIPT_DIR / ".env"
        if env.exists():
            for line in env.read_text().splitlines():
                if line.strip().startswith(f"{name}="):
                    val = line.split("=", 1)[1].strip()
    return val

# ---------------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------------

def _build_query(entry: dict) -> str:
    name     = entry.get("name", entry.get("polymarket_username", ""))
    company  = (entry.get("company") or "").strip()
    location = (entry.get("location") or "").strip()
    query = f'"{name}" site:linkedin.com/in/'
    if company:
        query += f' "{company}"'
    elif location:
        city = location.split(",")[0].strip()
        if city:
            query += f' "{city}"'
    return query

# ---------------------------------------------------------------------------
# Search backends
# ---------------------------------------------------------------------------

def _search_brave(query: str, timeout: int) -> tuple[str | None, str | None, str | None]:
    api_key = _load_env_key("BRAVE_API_KEY")
    if not api_key:
        raise RuntimeError("brave_api_key_missing")
    brave_usage.check(1)
    resp = requests.get(
        BRAVE_URL,
        headers={"Accept": "application/json", "Accept-Encoding": "gzip", "X-Subscription-Token": api_key},
        params={"q": query, "count": 5, "search_lang": "en", "country": "us"},
        timeout=timeout,
    )
    if resp.status_code == 401:
        raise RuntimeError("brave_api_key_invalid")
    if resp.status_code in (429, 422):
        raise RuntimeError("rate_limited")
    brave_usage.increment(1)
    for item in resp.json().get("web", {}).get("results", []):
        url = item.get("url", "").rstrip("/")
        if _is_linkedin_profile_url(url):
            return url, item.get("title"), item.get("description", "")[:280]
    return None, None, None

def _search_bing(query: str, timeout: int) -> tuple[str | None, str | None, str | None]:
    resp = requests.get(
        BING_URL,
        params={"q": query, "count": 10},
        headers={"User-Agent": random.choice(_USER_AGENTS), "Accept-Language": "en-US,en;q=0.9"},
        timeout=timeout,
    )
    if resp.status_code == 429:
        raise RuntimeError("rate_limited")
    html = resp.text
    if any(s in html.lower() for s in ("captcha", "unusual traffic")):
        raise RuntimeError("rate_limited")
    for block in re.split(r'<li\s+class="b_algo"', html)[1:]:
        m = re.search(r'<h2[^>]*>.*?<a\s+href="(https?://[^"]+)"', block, re.S)
        if not m:
            continue
        url = unquote(m.group(1)).rstrip("/")
        if _is_linkedin_profile_url(url):
            title_m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.S)
            snip_m  = re.search(r'<p\b[^>]*>(.*?)</p>', block, re.S)
            return url, (_clean(_strip_tags(title_m.group(1))) if title_m else None), (_clean(_strip_tags(snip_m.group(1))) if snip_m else None)
    return None, None, None

def _search_google(query: str, timeout: int) -> tuple[str | None, str | None, str | None]:
    api_key = _load_env_key("GOOGLE_API_KEY")
    cse_id  = _load_env_key("GOOGLE_CSE_ID")
    if not api_key:
        raise RuntimeError("google_api_key_missing")
    if not cse_id:
        raise RuntimeError("google_cse_id_missing")
    resp = requests.get(GOOGLE_CSE_URL, params={"key": api_key, "cx": cse_id, "q": query, "num": 5}, timeout=timeout)
    if resp.status_code == 429:
        raise RuntimeError("rate_limited")
    if resp.status_code == 403:
        raise RuntimeError("google_quota_exceeded")
    for item in resp.json().get("items", []):
        url = item.get("link", "").rstrip("/")
        if _is_linkedin_profile_url(url):
            return url, item.get("title"), item.get("snippet", "")[:280]
    return None, None, None

def _search_ddg(query: str, timeout: int) -> tuple[str | None, str | None, str | None]:
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    try:
        from playwright_stealth import Stealth
        stealth_ctx = Stealth()
    except ImportError:
        stealth_ctx = None
    url = f"{DDG_HTML_URL}?q={quote_plus(query)}"
    pw_base = sync_playwright()
    ctx = stealth_ctx.use_sync(pw_base) if stealth_ctx else pw_base
    with ctx as pw:
        browser = pw.chromium.launch(headless=True, args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = browser.new_context(user_agent=random.choice(_USER_AGENTS)).new_page()
        try:
            page.goto(url, wait_until="load", timeout=timeout * 1000)
        except PWTimeout:
            browser.close()
            raise RuntimeError("page_load_timeout")
        html = page.content()
        browser.close()
    if any(s in html.lower() for s in ("captcha", "bots use duckduckgo")):
        raise RuntimeError("rate_limited")
    for block in re.split(r'class="result__title"', html)[1:]:
        m = re.search(r'uddg=(https?://(?:www\.)?linkedin\.com/in/[^&"\']+)', block)
        if m:
            profile_url = unquote(m.group(1)).rstrip("/")
            title_m = re.search(r'class="result__a"[^>]*>(.*?)</a>', block, re.S)
            snip_m  = re.search(r'class="result__snippet"[^>]*>(.*?)</(?:a|span|div)>', block, re.S)
            return profile_url, (_clean(_strip_tags(title_m.group(1))) if title_m else None), (_clean(_strip_tags(snip_m.group(1))) if snip_m else None)
    return None, None, None

def search_for_linkedin(query: str, engine: str, timeout: int) -> tuple[str | None, str | None, str | None]:
    if engine == "brave":
        return _search_brave(query, timeout)
    elif engine == "google":
        return _search_google(query, timeout)
    elif engine == "bing":
        return _search_bing(query, timeout)
    else:
        return _search_ddg(query, timeout)


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _checkpoint_path(queries_file: Path) -> Path:
    return queries_file.with_name(queries_file.stem + "_checkpoint.json")


def _load_checkpoint(queries_file: Path) -> set[str]:
    cp = _checkpoint_path(queries_file)
    if cp.exists():
        try:
            return set(json.loads(cp.read_text(encoding="utf-8")).get("completed", []))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def _save_checkpoint(queries_file: Path, completed: set[str]) -> None:
    cp = _checkpoint_path(queries_file)
    tmp = cp.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"completed": sorted(completed)}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(cp)


# ---------------------------------------------------------------------------
# Profile directory auto-detection
# ---------------------------------------------------------------------------

def _find_profiles_dir(queries_file: Path) -> Path | None:
    """
    Given results/<slug>_analysis/linkedin_queries.json, find the sibling
    directory that holds the per-user profile JSONs.

    Strategy: strip the '_analysis' suffix from the analysis dir name to get
    the base slug, then find sibling directories in results/ that start with
    that prefix and actually contain .json files.
    """
    analysis_dir = queries_file.parent
    results_dir  = analysis_dir.parent

    name = analysis_dir.name
    base = name[: -len("_analysis")] if name.endswith("_analysis") else name

    candidates = [
        d for d in results_dir.iterdir()
        if d.is_dir()
        and d != analysis_dir
        and d.name.startswith(base)
        and any(d.glob("*.json"))
    ]

    if not candidates:
        return None
    # Prefer an exact base match; otherwise take the first alphabetically.
    for c in candidates:
        if c.name == base:
            return c
    return sorted(candidates)[0]


# ---------------------------------------------------------------------------
# Profile update
# ---------------------------------------------------------------------------

def _update_user_profile(user_file: Path, linkedin_result: dict) -> bool:
    """
    Inject or replace the LinkedIn entry in the user's profile JSON.
    Returns True if the file was written.
    """
    if not user_file.exists():
        return False
    try:
        profile = json.loads(user_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False

    profiles = [p for p in profile.get("profiles", []) if p.get("site") != "LinkedIn"]
    profiles.append(linkedin_result)
    profile["profiles"] = profiles

    user_file.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch LinkedIn lookup from linkedin_queries.json → user profile JSONs."
    )
    parser.add_argument("queries_file", help="Path to linkedin_queries.json")
    parser.add_argument(
        "--engine",
        choices=["brave", "bing", "ddg", "google"],
        default="brave",
        help="Search backend: brave (default), bing, ddg (Playwright), google (CSE API)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=-1,
        help="Parallel workers (default: 10 for brave/google, 1 for bing/ddg).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=-1,
        help="Seconds between requests per worker (default: 0 for brave, random 5-10 s for bing/google, 15-25 s for ddg).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Request timeout in seconds (default: 30).",
    )
    parser.add_argument(
        "--profiles-dir",
        default=None,
        help="Directory containing per-user profile JSONs. Auto-detected if omitted.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print queries without making any network requests.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    queries_file = Path(args.queries_file)
    if not queries_file.exists():
        print(f"Error: {queries_file} not found", file=sys.stderr)
        return 1

    out_dir = queries_file.parent  # checkpoint files stay here

    if args.profiles_dir:
        profiles_dir = Path(args.profiles_dir)
        if not profiles_dir.is_dir():
            print(f"Error: --profiles-dir {profiles_dir} does not exist", file=sys.stderr)
            return 1
    else:
        profiles_dir = _find_profiles_dir(queries_file)
        if profiles_dir is None:
            print(
                f"Warning: could not auto-detect profiles directory — "
                f"profile JSONs will not be updated. Use --profiles-dir to specify it.",
                file=sys.stderr,
            )
            profiles_dir = out_dir
        else:
            print(f"Profiles directory: {profiles_dir}")

    entries: list[dict] = json.loads(queries_file.read_text(encoding="utf-8"))
    total = len(entries)

    completed = _load_checkpoint(queries_file)
    to_process = [e for e in entries if e["polymarket_username"] not in completed]

    print(f"Loaded {total} entries — {len(completed)} already done, {len(to_process)} remaining")

    if args.engine == "brave":
        print(brave_usage.status_line())
        if brave_usage.remaining() < len(to_process):
            print(
                f"  ⚠  Only {brave_usage.remaining()} Brave requests remain this month "
                f"but {len(to_process)} entries to process. Will stop at quota."
            )

    if not to_process:
        print("Nothing to do.")
        return 0

    engine = args.engine
    n_workers = args.workers if args.workers > 0 else (10 if engine in ("brave", "google") else 1)
    default_delay_range = (15, 25) if engine == "ddg" else (5, 10) if engine == "bing" else (0, 0)
    if args.delay >= 0:
        default_delay_range = (args.delay, args.delay)

    print(f"Workers: {n_workers}  Delay per worker: {default_delay_range[0]:.1f}–{default_delay_range[1]:.1f}s")

    found = skipped = errors = 0
    stop_event = threading.Event()
    cp_lock    = threading.Lock()
    print_lock = threading.Lock()
    counter    = [0]  # mutable int shared across threads

    def _log(*parts: str) -> None:
        with print_lock:
            print(*parts)

    def _process(idx_entry: tuple[int, dict]) -> None:
        i, entry = idx_entry
        if stop_event.is_set():
            return
        username = entry["polymarket_username"]
        confidence = entry.get("name_confidence", "high")
        query = _build_query(entry)

        with print_lock:
            print(f"[{i}/{len(to_process)}] {username!r} → {query}")

        if args.dry_run:
            with cp_lock:
                completed.add(username)
                counter[0] += 1
            return

        delay = random.uniform(*default_delay_range)
        if delay > 0:
            time.sleep(delay)

        nonlocal found, skipped, errors
        try:
            profile_url, title, snippet = search_for_linkedin(query, engine, args.timeout)
        except RuntimeError as exc:
            msg = str(exc)
            if "monthly_quota_exceeded" in msg:
                _log(f"  ✗ monthly quota reached — stopping.")
                stop_event.set()
                return
            if "missing" in msg or "quota" in msg or "invalid" in msg:
                _log(f"  ✗ config error: {msg} — stopping.")
                stop_event.set()
                return
            if "rate_limited" in msg:
                _log(f"  ✗ [{username!r}] rate limited — skipping")
            else:
                _log(f"  ✗ [{username!r}] error: {msg}")
            with cp_lock:
                errors += 1
            return
        except Exception as exc:
            _log(f"  ✗ [{username!r}] unexpected error: {exc}")
            with cp_lock:
                errors += 1
            return

        if not profile_url:
            _log(f"  – [{username!r}] not found")
            with cp_lock:
                skipped += 1
        else:
            slug = urlparse(profile_url).path.strip("/").split("/")[-1]
            result = {
                "site": "LinkedIn",
                "username": username,
                "profile_url": profile_url,
                "linkedin_slug": slug,
                "title": title,
                "snippet": snippet,
                "search_name": entry["name"],
                "name_confidence": confidence,
            }
            safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", username)
            user_file = profiles_dir / f"{safe_name}.json"
            written = _update_user_profile(user_file, result)
            _log(f"  ✓ [{username!r}] {profile_url}" + (" (profile updated)" if written else ""))
            with cp_lock:
                found += 1

        with cp_lock:
            completed.add(username)
            counter[0] += 1
            _save_checkpoint(queries_file, completed)

    with ThreadPoolExecutor(max_workers=n_workers) as pool:
        futures = {pool.submit(_process, (i, e)): e for i, e in enumerate(to_process, 1)}
        for fut in as_completed(futures):
            exc = fut.exception()
            if exc:
                _log(f"  ✗ thread error: {exc}")

    print(
        f"\nDone — {found} found, {skipped} not found, {errors} errors "
        f"(of {len(to_process)} processed)"
    )
    if engine == "brave":
        print(brave_usage.status_line())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
