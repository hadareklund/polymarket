#!/usr/bin/env python3
"""
run.py — End-to-end OSINT pipeline for a Polymarket event.

Steps:
  1. Fetch all on-chain holders and resolve to Polymarket usernames.
  2. Run Sherlock against every site that has a matching working script.
  3. For each username × claimed site, run the site-specific info script.
  4. Write one JSON file per username to results/<event-slug>/
"""
from __future__ import annotations

import argparse
import json
import random
import re
import resource
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

SCRIPT_DIR = Path(__file__).resolve().parent
WORKING_DIR = SCRIPT_DIR / "site_user_info_scripts" / "working"

console = Console(stderr=True)

# ---------------------------------------------------------------------------
# Anti-fingerprinting helpers
# ---------------------------------------------------------------------------

_USER_AGENTS = [
    # Chrome — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    # Firefox — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Firefox — Linux
    "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari — macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_6_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    # Edge — Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    # Chrome — Android
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.82 Mobile Safari/537.36",
    # Safari — iPhone
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1",
]


@contextmanager
def _spoof_ua(ua: str):
    """Patch requests.session so every request Sherlock fires uses the given UA.

    Sherlock sets headers per-request, but they all go through session.send()
    as PreparedRequests — intercepting there lets us override the UA after
    Sherlock has already merged its headers.
    """
    import requests
    import requests.sessions as _rs

    orig = _rs.session

    def _patched_session():
        s = orig()
        _orig_send = s.send

        def _send(req, **kwargs):
            req.headers["User-Agent"] = ua
            return _orig_send(req, **kwargs)

        s.send = _send
        return s

    _rs.session = _patched_session
    requests.session = _patched_session
    try:
        yield ua
    finally:
        _rs.session = orig
        requests.session = orig


def _inter_user_delay(base: float, elapsed_seconds: float) -> None:
    """Sleep a jittered amount that grows slightly the longer the run has been going."""
    if base <= 0:
        return
    # After 1 h ramp up by 50 %, after 3 h by 100 % — mimics natural slowdown
    multiplier = 1.0 + min(elapsed_seconds / 10800, 1.0)
    delay = random.uniform(base * 0.5, base * 2.0) * multiplier
    time.sleep(delay)

# Sherlock manifest site name → working script filename (stem)
SHERLOCK_TO_SCRIPT: dict[str, str] = {
    "About.me": "about_me_user_info",
    "AllMyLinks": "allMyLinks_user_info",
    "Anilist": "anilist_user_info",
    "Archive of Our Own": "archive_of_our_own_user_info",
    "Atcoder": "atcoder_user_info",
    "Behance": "behance_user_info",
    "BitBucket": "bitbucket_user_info",
    "Blitz Tactics": "blitztactics_user_info",
    "Bluesky": "bluesky_user_info",
    "BuyMeACoffee": "buymeacoffee_user_info",
    "BuzzFeed": "buzzfeed_user_info",
    "Car Talk Community": "cartalkcommunity_user_info",
    "CashApp": "cashapp_user_info",
    "Championat": "championat_user_info",
    "Chess": "chesscom_user_info",
    "Chollometro": "chollometro_user_info",
    "Codechef": "codechef_user_info",
    "Codeforces": "codeforces_user_info",
    "Codepen": "codepen_user_info",
    "Coders Rank": "codersrank_user_info",
    "Coderwall": "coderwall_user_info",
    "Codewars": "codewars_user_info",
    "Crowdin": "crowdin_user_info",
    "DEV Community": "dev_community_user_info",
    "DailyMotion": "dailymotion_user_info",
    "Dealabs": "dealabs_user_info",
    "Discogs": "discogs_user_info",
    "Docker Hub": "dockerhub_user_info",
    "Dribbble": "dribbble_user_info",
    "Duolingo": "duolingo_user_info",
    "Flickr": "flickr_user_info",
    "Flipboard": "flipboard_user_info",
    "GaiaOnline": "gaiaonline_user_info",
    "GitHub": "github_user_info",
    "GitLab": "gitlab_user_info",
    "Gitee": "gitee_user_info",
    "GoodReads": "goodreads_user_info",
    "Grailed": "grailed_user_info",
    "Gumroad": "gumroad_user_info",
    "Gutefrage": "gutefrage_user_info",
    "HackMD": "hackmd_user_info",
    "HackerNews": "hackernews_user_info",
    "HackerOne": "hackerone_user_info",
    "Hive Blog": "hive_blog_user_info",
    "Houzz": "houzz_user_info",
    "HudsonRock": "hudsonrock_user_info",
    "Hugging Face": "huggingface_user_info",
    "Keybase": "keybase_user_info",
    "Kongregate": "kongregate_user_info",
    "Launchpad": "launchpad_user_info",
    "LeetCode": "leetcode_user_info",
    "LemmyWorld": "lemmyworld_user_info",
    "Letterboxd": "letterboxd_user_info",
    "Lichess": "lichess_user_info",
    "Linktree": "linktree_user_info",
    "LiveJournal": "livejournal_user_info",
    "Mamot": "mamot_user_info",
    "Medium": "medium_user_info",
    "MixCloud": "mixcloud_user_info",
    "Monkeytype": "monkeytype_user_info",
    "MyAnimeList": "myanimelist_user_info",
    "Mydealz": "mydealz_user_info",
    "Naver": "naver_user_info",
    "NintendoLife": "nintendolife_user_info",
    "Odysee": "odysee_user_info",
    "Open Collective": "opencollective_user_info",
    "Packagist": "packagist_user_info",
    "Pastebin": "pastebin_user_info",
    "PepperPL": "pepperpl_user_info",
    "Plurk": "plurk_user_info",
    "Pokemon Showdown": "pokemon_showdown_user_info",
    "ProductHunt": "producthunt_user_info",
    "Promodescuentos": "promodescuentos_user_info",
    "ReverbNation": "reverbnation_user_info",
    "RuneScape": "runescape_user_info",
    "SWAPD": "swapd_user_info",
    "Scratch": "scratch_user_info",
    "Sketchfab": "sketchfab_user_info",
    "Snapchat": "snapchat_user_info",
    "SoundCloud": "soundcloud_user_info",
    "SpeakerDeck": "speakerdeck_user_info",
    "Star Citizen": "star_citizen_user_info",
    "SublimeForum": "sublimeforum_user_info",
    "TETR.IO": "tetrio_user_info",
    "Telegram": "telegram_user_info",
    "Tiendanube": "tiendanube_user_info",
    "TradingView": "tradingview_user_info",
    "Tuna": "tuna_user_info",
    "Typeracer": "typeracer_user_info",
    "Ultimate-Guitar": "ultimate_guitar_user_info",
    "Untappd": "untappd_user_info",
    "Warrior Forum": "warrior_forum_user_info",
    "Wattpad": "wattpad_user_info",
    "Weebly": "weebly_user_info",
    "Wikidot": "wikidot_user_info",
    "Wikipedia": "wikipedia_user_info",
    "WordPress": "wordpress_user_info",
    "Wykop": "wykop_user_info",
    "akniga": "akniga_user_info",
    "couchsurfing": "couchsurfing_user_info",
    "d3RU": "d3ru_user_info",
    "dcinside": "dcinside_user_info",
    "drive2": "drive2_user_info",
    "furaffinity": "furaffinity_user_info",
    "habr": "habr_user_info",
    "kwork": "kwork_user_info",
    "last.fm": "lastfm_user_info",
    "mastodon.cloud": "mastodon_cloud_user_info",
    "mastodon.social": "mastodon_social_user_info",
    "omg.lol": "omg_lol_user_info",
    "osu!": "osu_user_info",
    "pikabu": "pikabu_user_info",
    "tistory": "tistory_user_info",
    "tumblr": "tumblr_user_info",
    "write.as": "write_as_user_info",
}

# Sites in our working/ folder that are NOT in Sherlock — always run them.
ALWAYS_RUN_SCRIPTS: list[str] = [
    "hudsonrock_user_info",   # breach exposure — always useful
]

# Output "site" names produced by ALWAYS_RUN_SCRIPTS (used to detect thin profiles).
_ALWAYS_RUN_SITE_NAMES: frozenset[str] = frozenset({"HudsonRock"})

# Max concurrent subprocess calls per site script stem.
# Medium-risk sites (official APIs with tighter limits) get 3; everything else gets 10.
_SITE_CONCURRENCY: dict[str, int] = {
    "github_user_info": 3,
    "gitlab_user_info": 3,
    "bitbucket_user_info": 3,
    "chesscom_user_info": 3,
    "codewars_user_info": 3,
    "dailymotion_user_info": 3,
    "discogs_user_info": 3,
    "mixcloud_user_info": 3,
}
_DEFAULT_SITE_CONCURRENCY = 10
_semaphore_lock = threading.Lock()
_site_semaphores: dict[str, threading.Semaphore] = {}


def _site_semaphore(stem: str) -> threading.Semaphore:
    with _semaphore_lock:
        if stem not in _site_semaphores:
            limit = _SITE_CONCURRENCY.get(stem, _DEFAULT_SITE_CONCURRENCY)
            _site_semaphores[stem] = threading.Semaphore(limit)
        return _site_semaphores[stem]


def _is_thin_profile(profile: dict) -> bool:
    """Return True if the profile contains nothing beyond always-run script results."""
    if profile.get("sherlock_claimed"):
        return False
    return all(
        p.get("site") in _ALWAYS_RUN_SITE_NAMES
        for p in profile.get("profiles", [])
    )


def log(msg: str) -> None:
    console.log(msg)


def safe_slug(text: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", text)


def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        BarColumn(bar_width=36),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=False,
    )


# ---------------------------------------------------------------------------
# Step 1: fetch usernames from Polymarket
# ---------------------------------------------------------------------------

def fetch_usernames(
    event_url: str, alchemy_key: str | None, workers: int
) -> tuple[list[str], str, dict[str, dict[str, bool]]]:
    """Run get_event_holder_usernames.py and return (all_usernames, slug, position_map).

    position_map: {username: {"yes": bool, "no": bool}}
    """
    cmd = [sys.executable, str(SCRIPT_DIR / "get_event_holder_usernames.py"), event_url]
    if alchemy_key:
        cmd += ["--alchemy-api-key", alchemy_key]
    if workers:
        cmd += ["--workers", str(workers)]

    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )

    # Stream stderr live so progress is visible, while collecting for parsing.
    stderr_lines: list[str] = []

    def _stream_stderr() -> None:
        assert proc.stderr
        for raw in proc.stderr:
            line = raw.rstrip("\n")
            stderr_lines.append(line)
            console.log(f"[dim]{line}[/]")

    t = threading.Thread(target=_stream_stderr, daemon=True)
    t.start()
    proc.wait()
    t.join()

    if proc.returncode != 0:
        raise RuntimeError("get_event_holder_usernames.py failed")

    # Find output file path in collected stderr
    output_file: str | None = None
    slug: str = "market"
    for line in stderr_lines:
        m = re.search(r"Wrote dataset to:\s*(.+)", line)
        if m:
            output_file = m.group(1).strip()
        m2 = re.search(r"Resolved event slug:\s*(.+)", line)
        if m2:
            slug = m2.group(1).strip()

    if not output_file:
        for line in stderr_lines:
            m = re.search(r"(/[^\s]+\.txt|results/[^\s]+\.txt)", line)
            if m:
                candidate = m.group(1)
                if not candidate.startswith("/"):
                    candidate = str(SCRIPT_DIR / candidate)
                output_file = candidate
                break

    if not output_file or not Path(output_file).exists():
        raise RuntimeError(f"Could not find usernames output file. Stderr:\n{proc.stderr}")

    fname = Path(output_file).stem
    slug_m = re.match(r"(.+?)_full_holder_usernames", fname)
    if slug_m:
        slug = slug_m.group(1)

    # Parse Yes/No sections: blank line separates Yes holders (above) from No holders (below)
    content = Path(output_file).read_text(encoding="utf-8")
    lines = content.splitlines()
    try:
        separator = lines.index("")
        yes_names = {u.strip() for u in lines[:separator] if u.strip()}
        no_names = {u.strip() for u in lines[separator + 1:] if u.strip()}
    except ValueError:
        yes_names = {u.strip() for u in lines if u.strip()}
        no_names: set[str] = set()

    all_usernames = list(yes_names | no_names)

    # Load per-market positions sidecar if available
    sidecar = Path(output_file).with_name(
        Path(output_file).stem.replace("_full_holder_usernames", "_market_positions") + ".json"
    )
    if sidecar.exists():
        raw_positions = json.loads(sidecar.read_text(encoding="utf-8"))
        position_map = {
            u: {
                "yes": u in yes_names,
                "no": u in no_names,
                "markets": [
                    {"slug": mslug, **mdata}
                    for mslug, mdata in raw_positions.get(u, {}).items()
                ],
            }
            for u in all_usernames
        }
    else:
        position_map = {
            u: {"yes": u in yes_names, "no": u in no_names}
            for u in all_usernames
        }

    return all_usernames, slug, position_map


# ---------------------------------------------------------------------------
# Step 2: run Sherlock
# ---------------------------------------------------------------------------

def run_sherlock(
    usernames: list[str],
    timeout: int,
    delay: float = 1.0,
    on_user_done: Callable[[], None] | None = None,
) -> dict[str, list[str]]:
    """Return {username: [claimed_sherlock_site_names]}.

    Uses a fresh random user-agent per username and adds a jittered inter-user
    delay to avoid behavioral fingerprinting across the run.
    """
    sherlock_root = SCRIPT_DIR / "sherlock"
    if not sherlock_root.exists():
        raise FileNotFoundError(
            "Sherlock submodule not found. Run: git submodule update --init --recursive"
        )
    if str(sherlock_root) not in sys.path:
        sys.path.insert(0, str(sherlock_root))

    from sherlock_project.sherlock import sherlock  # type: ignore
    from sherlock_project.sites import SitesInformation  # type: ignore
    from sherlock_project.notify import QueryNotifyPrint  # type: ignore

    manifest_path = sherlock_root / "sherlock_project" / "resources" / "data.json"
    sites_info = SitesInformation(data_file_path=str(manifest_path), honor_exclusions=False)
    all_site_data = {site.name: site.information for site in sites_info}

    target_site_names = [s for s in SHERLOCK_TO_SCRIPT if s in all_site_data]
    site_data = {name: all_site_data[name] for name in target_site_names}

    class _Silent:
        def start(self, *a, **kw): pass
        def update(self, *a, **kw): pass
        def finish(self, *a, **kw): pass

    claimed: dict[str, list[str]] = {}
    run_start = time.monotonic()

    for username in usernames:
        ua = random.choice(_USER_AGENTS)
        with _spoof_ua(ua):
            results = sherlock(
                username=username,
                site_data=site_data,
                query_notify=_Silent(),
                timeout=timeout,
            )

        found = [
            site for site in target_site_names
            if results[site]["status"].status.value == "Claimed"
        ]
        claimed[username] = found

        _inter_user_delay(delay, time.monotonic() - run_start)

        if on_user_done:
            on_user_done()

    return claimed


# ---------------------------------------------------------------------------
# Step 3: run site-specific scripts
# ---------------------------------------------------------------------------

def run_site_script(script_stem: str, username: str, timeout: int) -> dict | None:
    script_path = WORKING_DIR / f"{script_stem}.py"
    if not script_path.exists():
        return None
    with _site_semaphore(script_stem):
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), username, "--timeout", str(timeout)],
                capture_output=True,
                text=True,
                timeout=timeout + 10,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                data = json.loads(proc.stdout)
                if data.get("status") != "error":
                    return data
        except Exception:
            pass
    return None


def build_profile(
    username: str,
    claimed_sites: list[str],
    position: dict[str, bool],
    timeout: int,
    workers: int,
) -> dict:
    scripts_to_run: list[str] = list({
        SHERLOCK_TO_SCRIPT[site]
        for site in claimed_sites
        if site in SHERLOCK_TO_SCRIPT
    } | set(ALWAYS_RUN_SCRIPTS))

    site_results: list[dict] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(run_site_script, stem, username, timeout): stem
            for stem in scripts_to_run
        }
        for fut in as_completed(futures):
            result = fut.result()
            if result:
                site_results.append(result)

    return {
        "username": username,
        "position": position,
        "sherlock_claimed": claimed_sites,
        "profiles": site_results,
    }


# ---------------------------------------------------------------------------
# Checkpoint helpers
# ---------------------------------------------------------------------------

def _load_checkpoint(out_dir: Path) -> set[str]:
    cp = out_dir / "checkpoint.json"
    if cp.exists():
        try:
            return set(json.loads(cp.read_text(encoding="utf-8")).get("completed", []))
        except (json.JSONDecodeError, OSError):
            pass
    return set()


def _update_checkpoint(out_dir: Path, completed: set[str]) -> None:
    tmp = out_dir / "checkpoint.tmp"
    tmp.write_text(
        json.dumps({"completed": sorted(completed)}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(out_dir / "checkpoint.json")


# ---------------------------------------------------------------------------
# Shared profiling helpers
# ---------------------------------------------------------------------------

def _profile_and_save(
    username: str,
    claimed: list[str],
    position: dict,
    timeout: int,
    site_workers: int,
    skip_sherlock: bool,
    out_dir: Path,
) -> tuple[dict, bool]:
    """Build and optionally persist a user profile. Returns (profile, was_written)."""
    if not claimed and not ALWAYS_RUN_SCRIPTS:
        profile: dict = {"username": username, "position": position, "sherlock_claimed": [], "profiles": []}
    else:
        profile = build_profile(username, claimed, position, timeout, site_workers)

    if skip_sherlock:
        profile["sherlock_claimed"] = [p["site"] for p in profile["profiles"]]

    thin = _is_thin_profile(profile)
    if not thin:
        out_file = out_dir / f"{safe_slug(username)}.json"
        out_file.write_text(json.dumps(profile, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return profile, not thin


def _run_profiling_phase(
    usernames: list[str],
    claimed_map: dict[str, list[str]],
    position_map: dict[str, dict],
    timeout: int,
    site_workers: int,
    user_workers: int,
    skip_sherlock: bool,
    out_dir: Path,
    progress: Progress,
    step_task: TaskID,
) -> tuple[list[dict], int, int]:
    """Profile all users in parallel with checkpoint/resume. Returns (all_profiles, written, skipped)."""
    completed = _load_checkpoint(out_dir)
    already_done = [u for u in usernames if u in completed]
    to_process = [u for u in usernames if u not in completed]

    if already_done:
        log(f"[dim]Resuming: {len(already_done)} already done, {len(to_process)} remaining[/]")

    all_profiles: list[dict] = []
    written = skipped = 0

    # Restore profiles for already-completed users without re-running them.
    for username in already_done:
        out_file = out_dir / f"{safe_slug(username)}.json"
        if out_file.exists():
            try:
                all_profiles.append(json.loads(out_file.read_text(encoding="utf-8")))
                written += 1
                continue
            except (json.JSONDecodeError, OSError):
                pass
        # Thin profile (no file written) — reconstruct a minimal entry.
        all_profiles.append({
            "username": username,
            "position": position_map.get(username, {"yes": False, "no": False}),
            "sherlock_claimed": [],
            "profiles": [],
        })
        skipped += 1

    if already_done:
        progress.update(step_task, advance=len(already_done))

    if not to_process:
        return all_profiles, written, skipped

    lock = threading.Lock()

    def _do(username: str) -> None:
        nonlocal written, skipped
        claimed = claimed_map.get(username, [])
        position = position_map.get(username, {"yes": False, "no": False})
        profile, saved = _profile_and_save(
            username, claimed, position, timeout, site_workers, skip_sherlock, out_dir
        )
        with lock:
            all_profiles.append(profile)
            completed.add(username)
            _update_checkpoint(out_dir, completed)
            if saved:
                written += 1
            else:
                skipped += 1
        progress.advance(step_task)

    executor = ThreadPoolExecutor(max_workers=user_workers)
    futures = {executor.submit(_do, u): u for u in to_process}
    interrupted = False
    try:
        for fut in as_completed(futures):
            fut.result()
    except KeyboardInterrupt:
        interrupted = True
        log(f"[yellow]Interrupted — waiting for in-flight users to finish…[/]")
        executor.shutdown(wait=True, cancel_futures=True)
        log(f"[yellow]Checkpoint saved ({len(completed)}/{len(usernames)} users done). Re-run to resume.[/]")
    else:
        executor.shutdown(wait=False)

    if interrupted:
        raise KeyboardInterrupt

    return all_profiles, written, skipped


# ---------------------------------------------------------------------------
# Single-market runner (used by both single and multi-market paths)
# ---------------------------------------------------------------------------

def _run_one_market(
    event_url: str,
    args: argparse.Namespace,
    progress: Progress,
    step_task: TaskID,
) -> tuple[Path, int, int, int]:
    """Run the full pipeline for one market URL. Returns (out_dir, written, skipped, total)."""

    # Step 1: fetch usernames
    progress.update(step_task, description="[yellow]Fetching holders…", total=1, completed=0)
    usernames, slug, position_map = fetch_usernames(event_url, args.alchemy_api_key, args.workers)
    progress.update(step_task, completed=1)
    log(f"[cyan]{slug}[/] — {len(usernames)} unique usernames")

    if not usernames:
        log(f"[cyan]{slug}[/] — no usernames found, skipping")
        return SCRIPT_DIR / "results" / slug, 0, 0, 0

    out_dir = SCRIPT_DIR / "results" / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 2: Sherlock
    if args.skip_sherlock:
        claimed_map: dict[str, list[str]] = {u: list(SHERLOCK_TO_SCRIPT.keys()) for u in usernames}
    else:
        progress.update(
            step_task,
            description=f"[cyan]Sherlock [{slug}]",
            total=len(usernames),
            completed=0,
        )
        claimed_map = run_sherlock(
            usernames,
            args.timeout,
            delay=args.delay,
            on_user_done=lambda: progress.advance(step_task),
        )

    # Step 3: build per-user profiles
    progress.update(
        step_task,
        description=f"[green]Profiling [{slug}]",
        total=len(usernames),
        completed=0,
    )
    all_profiles, written, skipped = _run_profiling_phase(
        usernames, claimed_map, position_map,
        args.timeout, args.workers, args.user_workers,
        args.skip_sherlock, out_dir, progress, step_task,
    )

    # Write summary
    summary = {
        "slug": slug,
        "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "total_users": len(all_profiles),
        "users_with_profiles": written,
        "users": all_profiles,
    }
    summary_file = out_dir / "summary.json"
    summary_file.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    log(
        f"[bold green]✓[/] [cyan]{slug}[/] — "
        f"{written} profile(s) written, {skipped} thin, summary → [dim]{summary_file}[/]"
    )
    return out_dir, written, skipped, len(all_profiles)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full OSINT pipeline: Polymarket event → per-user JSON profiles."
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("event_url", nargs="?", default="", help="Polymarket event or market URL")
    src.add_argument("--usernames-file", help="Skip holder fetch; use usernames from this file instead")
    src.add_argument("--markets-file", help="File with one Polymarket event URL per line; runs all sequentially")
    parser.add_argument("--alchemy-api-key", help="Alchemy API key (or set ALCHEMY_API_KEY env var)")
    parser.add_argument("--timeout", type=int, default=20, help="Per-request timeout in seconds (default: 20)")
    parser.add_argument("--workers", type=int, default=5, help="Concurrent site-script workers per user (default: 5)")
    parser.add_argument("--user-workers", type=int, default=8, help="Users to profile in parallel (default: 8)")
    parser.add_argument("--skip-sherlock", action="store_true", default=True, help="Skip Sherlock and run all site scripts for every username (default: True)")
    parser.add_argument("--with-sherlock", dest="skip_sherlock", action="store_false", help="Enable Sherlock probing before running site scripts")
    parser.add_argument("--delay", type=float, default=1.0, help="Base inter-user delay in seconds between Sherlock checks (default: 1.0, 0 to disable)")
    return parser.parse_args()


def _raise_fd_limit(target: int = 4096) -> None:
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft < target:
        resource.setrlimit(resource.RLIMIT_NOFILE, (min(target, hard), hard))


def main() -> int:
    _raise_fd_limit()
    args = parse_args()

    # ── Multi-market mode ────────────────────────────────────────────────────
    if args.markets_file:
        raw = Path(args.markets_file).read_text(encoding="utf-8").splitlines()
        market_urls = [l.strip() for l in raw if l.strip() and not l.strip().startswith("#")]
        if not market_urls:
            console.print("[red]No market URLs found in file.[/]")
            return 2

        console.print(Panel(
            f"[bold]Processing [cyan]{len(market_urls)}[/] market(s)[/] from [dim]{args.markets_file}[/]",
            title="[bold blue]Polymarket OSINT Pipeline[/]",
            expand=False,
        ))

        try:
            with _make_progress() as progress:
                markets_task = progress.add_task("[bold blue]Markets", total=len(market_urls))
                step_task = progress.add_task("", total=1, completed=0)

                for i, url in enumerate(market_urls, 1):
                    progress.update(
                        markets_task,
                        description=f"[bold blue]Markets  [dim]({i}/{len(market_urls)})[/]",
                    )
                    try:
                        out_dir, written, skipped, total = _run_one_market(url, args, progress, step_task)
                        console.print(f"  [dim]→ {out_dir}[/]")
                    except KeyboardInterrupt:
                        raise
                    except Exception as exc:
                        console.print(f"[red]  ✗ {url}: {exc}[/]")
                    progress.advance(markets_task)
        except KeyboardInterrupt:
            console.print("\n[yellow]Run interrupted. Re-run the same command to resume from the checkpoint.[/]")
            return 1

        return 0

    # ── Single-market mode ───────────────────────────────────────────────────
    console.print(Panel("[bold blue]Polymarket OSINT Pipeline[/]", expand=False))

    try:
        with _make_progress() as progress:
            step_task = progress.add_task("", total=1, completed=0)

            if args.usernames_file:
                content = Path(args.usernames_file).read_text(encoding="utf-8")
                lines = content.splitlines()
                try:
                    separator = lines.index("")
                    yes_names = {u.strip() for u in lines[:separator] if u.strip()}
                    no_names = {u.strip() for u in lines[separator + 1:] if u.strip()}
                except ValueError:
                    yes_names = {u.strip() for u in lines if u.strip()}
                    no_names = set()

                usernames = list(yes_names | no_names)
                position_map = {u: {"yes": u in yes_names, "no": u in no_names} for u in usernames}
                slug = safe_slug(Path(args.usernames_file).stem)
                log(f"Loaded {len(usernames)} usernames from {args.usernames_file}")

                if not usernames:
                    log("No usernames found — nothing to do.")
                    return 0

                out_dir = SCRIPT_DIR / "results" / slug
                out_dir.mkdir(parents=True, exist_ok=True)

                if args.skip_sherlock:
                    claimed_map: dict[str, list[str]] = {u: list(SHERLOCK_TO_SCRIPT.keys()) for u in usernames}
                else:
                    progress.update(step_task, description="[cyan]Sherlock", total=len(usernames), completed=0)
                    claimed_map = run_sherlock(
                        usernames, args.timeout,
                        delay=args.delay,
                        on_user_done=lambda: progress.advance(step_task),
                    )

                progress.update(step_task, description="[green]Profiling", total=len(usernames), completed=0)
                all_profiles, written, skipped = _run_profiling_phase(
                    usernames, claimed_map, position_map,
                    args.timeout, args.workers, args.user_workers,
                    args.skip_sherlock, out_dir, progress, step_task,
                )

                summary = {
                    "slug": slug,
                    "generated_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "total_users": len(all_profiles),
                    "users_with_profiles": written,
                    "users": all_profiles,
                }
                (out_dir / "summary.json").write_text(
                    json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                log(f"Done. {written} profile(s), {skipped} thin. → {out_dir}/")
                print(str(out_dir))

            elif args.event_url:
                out_dir, written, skipped, total = _run_one_market(
                    args.event_url, args, progress, step_task
                )
                print(str(out_dir))

            else:
                console.print("[red]error:[/] provide event_url, --usernames-file, or --markets-file")
                return 2

    except KeyboardInterrupt:
        console.print("\n[yellow]Run interrupted. Re-run the same command to resume from the checkpoint.[/]")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
