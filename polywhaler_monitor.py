#!/usr/bin/env python3
"""
polywhaler_monitor.py — Daily poll of polywhaler.com whale trade feed.

1. Fetch high-insiderScore trades across all Polymarket markets.
2. Queue new wallets/usernames for OSINT (calls run.py --usernames-file).
3. Score each trader against the specific market they bet on.
4. Write a ranked report per market.

State:  results/polywhaler/state.json
Output: results/polywhaler/YYYY-MM-DD/
          trades.json      raw flagged trades for that day
          analysis.json    per-trader market-aware insider scores
          report.txt       human-readable ranked summary

Usage:
    python3 polywhaler_monitor.py                  # full run
    python3 polywhaler_monitor.py --threshold 15   # lower score cutoff
    python3 polywhaler_monitor.py --no-osint        # skip OSINT, analyze only
    python3 polywhaler_monitor.py --dry-run         # print what would be queued
    python3 polywhaler_monitor.py --pages 8         # fetch more pages of trades
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import falcon_analytics
import scoring
import sybil_clustering

SCRIPT_DIR     = Path(__file__).resolve().parent
STATE_FILE     = SCRIPT_DIR / "results" / "polywhaler" / "state.json"
BLOCKLIST_FILE = SCRIPT_DIR / "blocklist.json"
TRADES_URL     = "https://www.polywhaler.com/api/trades?category=all"
_UA            = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------

def _get(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _UA})
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())
        except Exception as exc:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("unreachable")


def _find_previous_trades_json(polywhaler_dir: Path) -> Path | None:
    """Return the trades.json from the most recent previous dated run directory."""
    dated = sorted(
        [d for d in polywhaler_dir.iterdir()
         if d.is_dir() and re.match(r"\d{4}-\d{2}-\d{2}$", d.name)],
        key=lambda d: d.name,
        reverse=True,
    )
    for d in dated:
        f = d / "trades.json"
        if f.exists():
            return f
    return None


def fetch_trades(max_pages: int, threshold: int) -> list[dict]:
    """Fetch up to max_pages of the trade feed and return trades with insiderScore >= threshold."""
    trades: list[dict] = []
    cursor: int | None = None

    for page in range(1, max_pages + 1):
        url = TRADES_URL + (f"&cursor={cursor}" if cursor else "")
        data = _get(url)
        batch = data.get("trades", [])
        trades.extend(batch)
        pg = data.get("pagination", {})
        cursor = pg.get("nextCursor")
        if not pg.get("hasNextPage"):
            break
        time.sleep(0.15)

    # Deduplicate by transactionHash (same aggregated trade can appear on multiple pages)
    seen_hashes: set[str] = set()
    unique: list[dict] = []
    for t in trades:
        h = t.get("transactionHash", "")
        if h not in seen_hashes:
            seen_hashes.add(h)
            unique.append(t)

    return [t for t in unique if (t.get("insiderScore") or 0) >= threshold]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"seen_wallets": [], "last_fetch": None}


def load_blocklist() -> tuple[set[str], set[str]]:
    """Return (blocked_wallets, blocked_usernames) as lowercase sets."""
    if not BLOCKLIST_FILE.exists():
        return set(), set()
    try:
        data = json.loads(BLOCKLIST_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set(), set()
    wallets   = {w.lower() for w in data.get("wallets", {})}
    usernames = {u.lower() for u in data.get("usernames", {})}
    return wallets, usernames


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# OSINT — calls run.py for new usernames
# ---------------------------------------------------------------------------

def run_osint(
    usernames: list[str],
    out_dir: Path,
    args: argparse.Namespace,
    wallet_map: dict[str, str] | None = None,
) -> Path:
    """Write a usernames file (and optional wallet map) then call run.py --usernames-file."""
    names_file = out_dir / "new_usernames.txt"
    names_file.write_text("\n".join(usernames), encoding="utf-8")
    if wallet_map:
        wmap_file = out_dir / "new_usernames_wallet_map.json"
        wmap_file.write_text(json.dumps(wallet_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Running OSINT on {len(usernames)} new trader(s)…", flush=True)

    cmd = [
        sys.executable, str(SCRIPT_DIR / "run.py"),
        "--usernames-file", str(names_file),
        "--timeout",      str(args.timeout),
        "--workers",      str(args.workers),
        "--user-workers", str(args.user_workers),
    ]
    if args.skip_sherlock:
        cmd.append("--skip-sherlock")

    proc = subprocess.run(cmd, text=True)
    if proc.returncode == 1:
        print(f"  Warning: run.py interrupted (partial data checkpointed)", file=sys.stderr)
    elif proc.returncode > 1:
        raise RuntimeError(
            f"run.py crashed (exit {proc.returncode}) — aborting to avoid scoring corrupted data"
        )

    # run.py writes to results/<stem of names_file>
    profiles_dir = SCRIPT_DIR / "results" / names_file.stem
    return profiles_dir


def load_profiles(profiles_dir: Path) -> dict[str, dict]:
    """Return {username: profile_dict} from a profiles directory."""
    profiles: dict[str, dict] = {}
    if not profiles_dir.is_dir():
        return profiles
    for f in profiles_dir.glob("*.json"):
        if f.name in ("checkpoint.json", "summary.json"):
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            u = data.get("username")
            if u:
                profiles[u] = data
        except (json.JSONDecodeError, OSError):
            pass
    return profiles


# ---------------------------------------------------------------------------
# Market-aware insider analysis
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# LinkedIn enrichment — query building (mirrors build_linkedin_queries.py)
# ---------------------------------------------------------------------------

_NAME_PRIORITY = [
    ("GitHub",          "name"),
    ("chess.com",       "name"),
    ("Hugging Face",    "full_name"),
    ("Lichess",         "real_name"),
    ("Keybase",         "full_name"),
    ("Docker Hub",      "full_name"),
    ("LeetCode",        "name"),
    ("DEV Community",   "name"),
    ("Product Hunt",    "name"),
    ("Dribbble",        "name"),
    ("Codewars",        "name"),
    ("Coderwall",       "name"),
    ("Open Collective", "name"),
    ("Crowdin",         "name"),
    ("Discogs",         "name"),
    ("Couchsurfing",    "name"),
    ("Wattpad",         "name"),
]

_CJK_RE = re.compile(r"[一-鿿぀-ヿ가-힯؀-ۿऀ-ॿ]")
_REJECT_WORDS = {
    "inc", "llc", "ltd", "corp", "university", "institute",
    "school", "college", "studio", "labs", "lab", "team",
    "official", "account", "user", "null", "none", "test",
    "admin", "root", "anonymous", "unknown", "n/a",
}


def _looks_like_real_name(s: str) -> bool:
    if not s:
        return False
    s = " ".join(s.split())
    if len(s) < 4 or len(s) > 60:
        return False
    if "@" in s or "http" in s or "/" in s:
        return False
    parts = s.split()
    if len(parts) < 2:
        return False
    for p in parts:
        if p.isdigit():
            return False
        if len(p) > 4 and p.isupper():
            return False
    low = s.lower()
    if any(w in low.split() for w in _REJECT_WORDS):
        return False
    if _CJK_RE.search(s):
        return False
    return True


def _build_linkedin_entry(profile: dict) -> dict | None:
    """Extract name/company/location from a profile dict for LinkedIn search."""
    profiles_by_site = {p["site"]: p for p in profile.get("profiles", [])}

    chosen_name = None
    name_source = None

    cf = profiles_by_site.get("Codeforces")
    if cf:
        first = (cf.get("first_name") or "").strip()
        last  = (cf.get("last_name")  or "").strip()
        combined = f"{first} {last}".strip()
        if _looks_like_real_name(combined):
            chosen_name = " ".join(combined.split())
            name_source = "Codeforces"

    if not chosen_name:
        for site, field in _NAME_PRIORITY:
            p = profiles_by_site.get(site)
            if p:
                raw = (p.get(field) or "").strip()
                if _looks_like_real_name(raw):
                    chosen_name = " ".join(raw.split())
                    name_source = site
                    break

    if not chosen_name:
        return None

    company = ""
    gh = profiles_by_site.get("GitHub")
    if gh:
        raw_company = (gh.get("company") or "").strip()
        tokens = raw_company.split()
        first_tok = tokens[0].lstrip("@").rstrip(",.;") if tokens else ""
        if first_tok and first_tok.lower() not in ("none", "null", "n/a", "private", "at large"):
            company = first_tok

    location = ""
    for site in ("GitHub", "chess.com", "Duolingo"):
        p = profiles_by_site.get(site)
        if p:
            loc = (p.get("location") or "").strip()
            if loc and len(loc) <= 100:
                location = loc
                break

    parts = chosen_name.split()
    name_confidence = "high" if len(parts) >= 2 and len(parts[-1]) > 1 else "low"

    return {
        "polymarket_username": profile["username"],
        "name":            chosen_name,
        "name_source":     name_source,
        "name_confidence": name_confidence,
        "company":         company,
        "location":        location,
    }


def run_linkedin(profiles: dict[str, dict], profiles_dir: Path, out_dir: Path, engine: str) -> int:
    """Build LinkedIn queries from loaded profiles and run linkedin_batch.py.

    linkedin_batch.py updates the per-user profile JSONs in-place, so profiles
    must be reloaded after this call to pick up the new LinkedIn data.
    Returns the number of entries submitted.
    """
    queries: list[dict] = []
    for profile in profiles.values():
        entry = _build_linkedin_entry(profile)
        if entry:
            queries.append(entry)

    if not queries:
        print("  LinkedIn: no profiles with usable real names — skipping.")
        return 0

    queries_file = out_dir / "linkedin_queries.json"
    queries_file.write_text(json.dumps(queries, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  LinkedIn: {len(queries)} quer{'y' if len(queries) == 1 else 'ies'} → {queries_file}")

    cmd = [
        sys.executable, str(SCRIPT_DIR / "linkedin_batch.py"),
        str(queries_file),
        "--engine",       engine,
        "--profiles-dir", str(profiles_dir),
    ]
    proc = subprocess.run(cmd, text=True)
    if proc.returncode == 1:
        print(f"  Warning: linkedin_batch.py interrupted (partial results)", file=sys.stderr)
    elif proc.returncode > 1:
        print(f"  Warning: linkedin_batch.py crashed (exit {proc.returncode})", file=sys.stderr)

    return len(queries)


# ---------------------------------------------------------------------------
# Market-aware insider analysis
# ---------------------------------------------------------------------------

# Finance lists and text utilities live in scoring.py (shared with analyze_insider_trading.py).
INVESTMENT_BANKS = scoring.INVESTMENT_BANKS
VC_FIRMS         = scoring.VC_FIRMS
SECURITIES_LAW   = scoring.SECURITIES_LAW
_INV_TERMS = (
    "capital", "venture", " fund", "hedge fund", "asset management",
    "investment", "trading firm", "private equity", "growth equity",
    "family office", "partners",
)

# ── Category-specific professional signals ─────────────────────────────────

CATEGORY_KEYWORDS: dict[str, list[str]] = {
    "politics": [
        "state department", "department of state", "foreign service",
        "national security council", "nsc", "central intelligence agency", "cia",
        "intelligence agency", "embassy", "diplomat", "ambassador",
        "senator", "congressman", "parliament", "white house",
        "council on foreign relations", "brookings", "rand corporation",
        "policy institute", "ministry of foreign", "foreign ministry",
    ],
    "crypto": [
        "binance", "coinbase", "kraken", "gemini", "okx", "bybit", "bitfinex",
        "solana", "ethereum foundation", "bitcoin", "blockchain", "defi",
        "web3", "crypto exchange", "market maker", "jump crypto", "wintermute",
    ],
    "finance": [
        "federal reserve", "treasury department", "central bank", "ecb",
        "bank of england", "imf", "world bank", "cbo", "economist",
        "federal open market committee", "fomc",
    ],
    "science": [
        "cdc", "nih", "fda", "who ", "world health organization",
        "pharmaceutical", "clinical trial", "biotech", "research institute",
    ],
}

# ── Entity extraction from market title ────────────────────────────────────

_TITLE_STOP = {
    "will", "the", "a", "an", "is", "are", "was", "were", "be", "been",
    "have", "has", "had", "do", "does", "did", "for", "in", "on", "at",
    "by", "with", "to", "from", "and", "or", "but", "not", "no", "yes",
    "if", "that", "this", "it", "of", "before", "after", "until", "since",
    "end", "hit", "win", "one", "two", "new", "day", "may", "june", "july",
    "april", "march", "january", "february", "august", "september",
    "october", "november", "december", "above", "below", "between",
    "next", "last", "first", "long", "high", "low", "still", "again",
    "any", "all", "each", "per", "out", "up", "down", "normal", "change",
}

_KNOWN_ORGS = re.compile(
    r"\b(US|UK|EU|UN|NATO|IMF|WHO|WTO|FBI|CIA|NSA|NSC|Fed|SEC|ECB|"
    r"FOMC|USDA|EPA|DOD|DOJ|DOE|DOGE)\b"
)


def extract_market_entities(title: str) -> list[str]:
    """Extract named entities from a market title for professional-field matching."""
    entities: list[str] = []

    # Known acronyms
    for m in _KNOWN_ORGS.finditer(title):
        entities.append(m.group().lower())

    # Runs of Title-Case words
    for m in re.finditer(r"(?:[A-Z][a-z]{1,}\s*){2,}", title):
        phrase = m.group().strip().lower()
        words = phrase.split()
        if not all(w in _TITLE_STOP for w in words) and len(phrase) >= 4:
            entities.append(phrase)

    # CamelCase identifiers (crypto tokens etc.)
    for m in re.finditer(r"\b[A-Z][a-z]+[A-Z][a-zA-Z]+\b", title):
        entities.append(m.group().lower())

    return list(dict.fromkeys(entities))  # deduplicated, order-preserving


def _minutes_before_resolution(trade: dict) -> float | None:
    """Return how many minutes before market resolution the trade was placed.

    Uses firstTradeTimestamp (earliest trade in an aggregated batch) for
    accuracy. Returns None if the market hasn't resolved yet or data is missing.
    """
    end_date_str = trade.get("endDate")
    if not end_date_str:
        return None
    try:
        end_dt = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        if end_dt > now:
            return None  # market still open — timing signal not applicable
        ts_raw = trade.get("firstTradeTimestamp") or trade.get("timestamp")
        if not ts_raw:
            return None
        trade_dt = datetime.fromtimestamp(
            ts_raw / 1000 if ts_raw > 1e12 else float(ts_raw),
            tz=timezone.utc,
        )
        minutes = (end_dt - trade_dt).total_seconds() / 60
        return minutes if minutes >= 0 else None  # ignore trades after resolution
    except (ValueError, TypeError, OSError):
        return None


def _extract_identity_summary(profile: dict) -> dict:
    """Extract real name, employer, and LinkedIn link from a scraped profile."""
    profiles_by_site = {p["site"]: p for p in profile.get("profiles", [])}
    out: dict = {}

    li = profiles_by_site.get("LinkedIn")
    if li:
        title_str = li.get("title", "")
        name = ""
        employer = ""

        # Parse title: "First Last - Employer | LinkedIn" — most reliable source
        if title_str and " | LinkedIn" in title_str:
            inner = title_str.split(" | LinkedIn")[0]
            if " - " in inner:
                name = inner.split(" - ")[0].strip()
                employer = inner.split(" - ", 1)[-1].strip()

        # Fall back to search_name only if title parse failed and it looks like a person
        if not name:
            sn = (li.get("search_name") or "").strip()
            if _looks_like_real_name(sn):
                name = sn

        if name:
            out["real_name"] = name
            out["name_source"] = "LinkedIn"
        if employer and employer != name:
            out["employer"] = employer

        if li.get("profile_url"):
            out["linkedin_url"] = li["profile_url"]

        snippet = (li.get("snippet") or "").strip()
        if snippet and len(snippet) > 30:
            snippet = re.sub(r"<[^>]+>", " ", snippet)
            snippet = re.sub(r"\s+", " ", snippet).strip()[:200]
            out["linkedin_snippet"] = snippet

    gh = profiles_by_site.get("GitHub")
    if gh:
        company = (gh.get("company") or "").strip()
        tokens = company.split()
        first_tok = tokens[0].lstrip("@").rstrip(",.;") if tokens else ""
        if first_tok and first_tok.lower() not in ("none", "null", "n/a", "private"):
            if not out.get("employer"):
                out["github_company"] = first_tok
        if not out.get("real_name"):
            raw = (gh.get("name") or "").strip()
            if _looks_like_real_name(raw):
                out["real_name"] = raw
                out["name_source"] = "GitHub"

    if not out.get("real_name"):
        for site, field in [("Hugging Face", "full_name"), ("chess.com", "name"),
                            ("LeetCode", "name"), ("DEV Community", "name")]:
            p = profiles_by_site.get(site)
            if p:
                raw = (p.get(field) or "").strip()
                if _looks_like_real_name(raw):
                    out["real_name"] = raw
                    out["name_source"] = site
                    break

    return out


def score_against_market(
    username: str,
    profile: dict,
    trade: dict,
    osint_ran: bool = False,
) -> dict:
    """Score a single trader against the market they bet on.

    osint_ran: True when a real OSINT profile was loaded from disk for this
    trader — enables the ghost-account penalty for profiles with no hits.
    """
    prof_fields = scoring.prof_fields_from_profile(profile)
    category    = (trade.get("category") or "").lower()
    title       = trade.get("title", "")
    outcome     = trade.get("outcome", "")
    size        = trade.get("size") or 0
    pw_score    = trade.get("insiderScore") or 0
    S           = scoring.SCORING

    flags: list[dict] = []
    score = 0

    # ── 1. Direct entity match ────────────────────────────────────────────
    entities = extract_market_entities(title)
    for entity in entities:
        hits = [(f, v) for f, v in prof_fields if scoring.kw_match(v, entity)]
        if hits:
            best_field, best_val = hits[0]
            via_linkedin = best_field == "LinkedIn.company"
            pts = S["direct_entity_match_linkedin_pts"] if via_linkedin else S["direct_entity_match_pts"]
            flags.append({
                "type": "direct_entity_match",
                "entity": entity,
                "field": best_field,
                "context": best_val[:80],
                "points": pts,
            })
            score += pts
            break  # one entity match per market is enough

    # ── 2. Category-specific professional keywords ────────────────────────
    cat_kws = CATEGORY_KEYWORDS.get(category, [])
    for kw in cat_kws:
        hits = [(f, v) for f, v in prof_fields if scoring.kw_match(v, kw)]
        if hits:
            best_field, best_val = hits[0]
            flags.append({
                "type": f"category_{category}_keyword",
                "keyword": kw,
                "field": best_field,
                "context": best_val[:80],
                "points": S["category_keyword_pts"],
            })
            score += S["category_keyword_pts"]
            break

    # ── 3. Finance infrastructure (universal) ─────────────────────────────
    def _check_list(kw_list: list[str], flag_type: str, pts: int) -> None:
        nonlocal score
        for kw in kw_list:
            hits = [(f, v) for f, v in prof_fields if scoring.kw_match(v, kw)]
            if hits:
                flags.append({
                    "type": flag_type,
                    "keyword": kw,
                    "context": hits[0][0] + ": " + hits[0][1][:80],
                    "points": pts,
                })
                score += pts
                return

    _check_list(INVESTMENT_BANKS, "investment_bank", S["investment_bank_pts"])
    _check_list(VC_FIRMS,         "vc_firm",         S["vc_firm_pts"])
    _check_list(SECURITIES_LAW,   "securities_law",  S["securities_law_pts"])

    # Generic investment firm term in company field
    for f, v in prof_fields:
        if f.endswith(".company"):
            term = next((t for t in _INV_TERMS if t in v.lower()), None)
            if term:
                flags.append({
                    "type": "investment_firm_company",
                    "company": v,
                    "matched_term": term,
                    "points": S["investment_firm_pts"],
                })
                score += S["investment_firm_pts"]
                break

    # ── 4. Polywhaler insider score as base signal ─────────────────────────
    # Map polywhaler's 0-100 score to 0-10 bonus points so it nudges ranking
    # without dominating over the OSINT signals.
    pw_bonus = min(10, pw_score // 6)
    if pw_bonus > 0:
        flags.append({"type": "polywhaler_insider_score", "raw": pw_score, "points": pw_bonus})
        score += pw_bonus

    # ── 5. Trade size signal ──────────────────────────────────────────────
    if size >= S["large_trade_usd"]:
        flags.append({"type": "large_trade", "size": size, "points": S["large_trade_pts"]})
        score += S["large_trade_pts"]
    elif size >= S["medium_trade_usd"]:
        flags.append({"type": "medium_trade", "size": size, "points": S["medium_trade_pts"]})
        score += S["medium_trade_pts"]

    # ── 6. Profile depth (only meaningful when OSINT was actually run) ────
    # osint_ran is True only for profiles loaded from disk, not synthetic empties.
    if osint_ran and not profile.get("profiles") and not profile.get("sherlock_claimed"):
        pts = S["no_online_presence_pts"]
        flags.append({"type": "no_online_presence", "points": pts})
        score += pts  # ghost account with insider score is suspicious

    # ── 7. Falcon on-chain analytics ─────────────────────────────────────
    falcon_f, falcon_s = scoring.falcon_flags(profile)
    flags.extend(falcon_f)
    score += falcon_s

    # ── 8. Pre-resolution timing ──────────────────────────────────────────
    minutes_before = _minutes_before_resolution(trade)
    if minutes_before is not None:
        if minutes_before < 1:
            pts = 4
        elif minutes_before < 10:
            pts = 3
        elif minutes_before < 30:
            pts = 2
        elif minutes_before < 60:
            pts = 1
        else:
            pts = 0
        if pts > 0:
            flags.append({
                "type": "pre_resolution_trade",
                "minutes_before_resolution": round(minutes_before, 1),
                "points": pts,
            })
            score += pts

    result: dict = {
        "username": username,
        "market_title": title,
        "market_category": category,
        "outcome": outcome,
        "trade_size": size,
        "polywhaler_insider_score": pw_score,
        "our_score": score,
        "flags": flags,
        "profiles_found": [p["site"] for p in profile.get("profiles", [])],
    }
    identity = _extract_identity_summary(profile)
    if identity:
        result["identity"] = identity
    analytics = profile.get("polymarket_analytics", {})
    if analytics:
        result["polymarket_analytics"] = analytics
    return result


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

def _flag_ctx(flag: dict) -> str:
    ftype = flag.get("type", "")
    if ftype == "large_portfolio":
        return f"${flag.get('portfolio_value', 0):,} portfolio value"
    if ftype == "concentrated_thesis":
        pct = flag.get("top_pct", 0)
        val = flag.get("top_value", 0)
        title = flag.get("top_title", "")
        return f"{pct:.0%} of portfolio (${val:,.0f}) in: {title[:50]}"
    if ftype == "falcon_large_pnl":
        return f"${flag.get('total_pnl', 0):,} lifetime PnL (legacy data)"
    if ftype == "falcon_high_roi":
        return f"{flag.get('roi_pct', 0)}% ROI over {flag.get('total_trades', 0)} trades"
    if ftype == "falcon_high_win_rate":
        pct = flag.get("win_rate", 0)
        win = flag.get("window_days")
        suffix = f" ({win}d window)" if win else ""
        return f"{float(pct):.1%} win rate{suffix}"
    if ftype == "falcon_high_sharpe":
        win = flag.get("window_days")
        suffix = f" ({win}d window)" if win else ""
        return f"Sharpe {flag.get('sharpe_ratio', 0)}{suffix}"
    if ftype == "falcon_concentrated_bets":
        win = flag.get("window_days")
        suffix = f" ({win}d window)" if win else ""
        return f"category diversity score {flag.get('diversity_score', 0)}{suffix}"
    if ftype == "pre_resolution_trade":
        m = flag.get("minutes_before_resolution", 0)
        if m < 1:
            return f"{m:.1f} min before market closed (< 1 min!)"
        return f"{m:.1f} min before market closed"
    if ftype == "sybil_cluster":
        peers = flag.get("cluster_peers", [])
        agg = flag.get("cluster_aggregate_usd")
        funders = flag.get("shared_funders", [])
        funder_str = ", ".join(f[:10] + "…" + f[-4:] for f in funders[:2])
        line = f"via {funder_str} → " if funder_str else ""
        line += ", ".join(peers[:3])
        if len(peers) > 3:
            line += f" +{len(peers) - 3} more"
        if agg:
            line += f" — cluster total ${agg:,.0f}"
        return line
    return (flag.get("context") or flag.get("company") or
            flag.get("keyword") or flag.get("entity") or
            str(flag.get("raw", "")))


def write_report(results: list[dict], out_dir: Path, date_str: str) -> Path:
    results_sorted = sorted(results, key=lambda x: -x["our_score"])

    report_lines = [
        f"POLYWHALER INSIDER MONITOR — {date_str}",
        f"{'='*72}",
        f"Traders scored: {len(results)}",
        "",
    ]

    for r in results_sorted[:40]:
        report_lines.append(
            f"  {r['username']:30s}  our={r['our_score']:3d}  "
            f"pw={r['polywhaler_insider_score']:3d}  "
            f"${r['trade_size']:>10,.0f}  {r['outcome']}  "
            f"{r['market_title'][:50]}"
        )
        # Show additional markets if the trader bet on more than one
        for extra in r.get("all_trades", [])[1:3]:
            report_lines.append(
                f"    also: ${extra['size']:>10,.0f}  {extra['outcome']}  {extra['title'][:55]}"
            )
        for flag in r["flags"]:
            ftype = flag["type"]
            pts   = flag.get("points", 0)
            ctx   = _flag_ctx(flag)
            report_lines.append(f"    [{pts:+d}] {ftype}: {ctx[:70]}")
        report_lines.append("")

    report = "\n".join(report_lines)
    report_file = out_dir / "report.txt"
    report_file.write_text(report, encoding="utf-8")
    print(report)
    return report_file


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily polywhaler insider monitor.")
    p.add_argument("--threshold",    type=int,   default=20,  help="Min insiderScore to queue (default: 20)")
    p.add_argument("--pages",        type=int,   default=4,   help="Max trade feed pages to fetch (default: 4 = ~200 trades)")
    p.add_argument("--no-osint",     action="store_true",     help="Skip OSINT, score existing profiles only")
    p.add_argument("--dry-run",      action="store_true",     help="Show new traders without running OSINT")
    p.add_argument("--timeout",      type=int,   default=20,  help="run.py --timeout (default: 20)")
    p.add_argument("--workers",      type=int,   default=5,   help="run.py --workers (default: 5)")
    p.add_argument("--user-workers", type=int,   default=8,   help="run.py --user-workers (default: 8)")
    p.add_argument("--skip-sherlock", action="store_true", default=True)
    p.add_argument("--with-sherlock", dest="skip_sherlock", action="store_false")
    p.add_argument("--no-linkedin",    action="store_true",  help="Skip LinkedIn enrichment step")
    p.add_argument("--linkedin-engine", default="brave",
                   choices=["brave", "bing", "ddg", "google"],
                   help="Search backend for LinkedIn lookup (default: brave)")
    p.add_argument("--no-sybil",       action="store_true",  help="Skip Sybil/shared-funder cluster analysis")
    p.add_argument("--sybil-lookback", type=int, default=90, help="Days of Polygon history to scan for shared funders (default: 90)")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir  = SCRIPT_DIR / "results" / "polywhaler" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Fetch (with fallback to previous day's data on total failure) ────────
    print(f"Fetching up to {args.pages} page(s) of trades (threshold: insiderScore ≥ {args.threshold})…")
    try:
        trades = fetch_trades(args.pages, args.threshold)
    except Exception as exc:
        print(f"  Fetch failed: {exc} — looking for previous trades.json…", file=sys.stderr)
        fallback = _find_previous_trades_json(out_dir.parent)
        if fallback is None:
            raise RuntimeError(f"Fetch failed and no previous trades.json found: {exc}") from exc
        print(f"  Using stale data from {fallback.parent.name}", file=sys.stderr)
        trades = json.loads(fallback.read_text(encoding="utf-8"))
    print(f"  {len(trades)} trades at or above threshold")

    trades_file = out_dir / "trades.json"
    trades_file.write_text(json.dumps(trades, indent=2, ensure_ascii=False), encoding="utf-8")

    if not trades:
        print("Nothing to do.")
        return 0

    # ── Dedup against seen wallets ────────────────────────────────────────
    state = load_state()
    seen_wallets: set[str] = set(state.get("seen_wallets", []))

    new_trades   = [t for t in trades if t.get("proxyWallet") not in seen_wallets]
    known_trades = [t for t in trades if t.get("proxyWallet") in seen_wallets]

    new_usernames: list[str] = []
    new_wallet_map: dict[str, str] = {}
    seen_names: set[str] = set()
    for t in new_trades:
        name = t.get("name")
        wallet = t.get("proxyWallet", "")
        if name and name not in seen_names and not name.startswith("0x"):
            new_usernames.append(name)
            seen_names.add(name)
            if wallet:
                new_wallet_map[name] = wallet.lower()

    print(f"  {len(new_trades)} new trader(s) not seen before, {len(known_trades)} already profiled")
    print(f"  {len(new_usernames)} username(s) to OSINT")

    # ── Blocklist filter (applied before OSINT so we don't waste scraping) ──
    blocked_wallets, blocked_usernames = load_blocklist()
    skipped_osint = 0
    skipped_score = 0
    if blocked_wallets or blocked_usernames:
        before = len(new_usernames)
        new_usernames = [
            u for u in new_usernames
            if u.lower() not in blocked_usernames
            and new_wallet_map.get(u, "").lower() not in blocked_wallets
        ]
        new_wallet_map = {u: w for u, w in new_wallet_map.items() if u in new_usernames}
        skipped_osint = before - len(new_usernames)
        if skipped_osint:
            print(f"  Blocklist: suppressed {skipped_osint} new trader(s) from OSINT")

    if args.dry_run:
        print("\nNew usernames that would be queued:")
        for u in new_usernames:
            matching = [t for t in new_trades if t.get("name") == u]
            t = matching[0]
            print(f"  {u:30s}  pw={t.get('insiderScore',0):3d}  ${t.get('size',0):>10,.0f}  {t['title'][:50]}")
        return 0

    # ── OSINT ─────────────────────────────────────────────────────────────
    profiles_dir: Path | None = None
    if new_usernames and not args.no_osint:
        profiles_dir = run_osint(new_usernames, out_dir, args, wallet_map=new_wallet_map)
    elif args.no_osint and new_usernames:
        # Point at wherever run.py would have written profiles
        names_file_stem = "new_usernames"
        profiles_dir = SCRIPT_DIR / "results" / names_file_stem

    # Update state: mark new wallets as seen
    new_wallets = {t.get("proxyWallet") for t in new_trades if t.get("proxyWallet")}
    state["seen_wallets"] = sorted(seen_wallets | new_wallets)
    state["last_fetch"] = datetime.now(timezone.utc).isoformat()
    save_state(state)

    # ── LinkedIn enrichment ───────────────────────────────────────────────
    if not args.no_linkedin and profiles_dir:
        profiles_pre = load_profiles(profiles_dir)
        if profiles_pre:
            run_linkedin(profiles_pre, profiles_dir, out_dir, args.linkedin_engine)
        else:
            print("  LinkedIn: no profiles loaded yet — skipping.")

    # ── Load profiles (includes LinkedIn data if enrichment ran) ──────────
    profiles: dict[str, dict] = {}
    if profiles_dir:
        profiles = load_profiles(profiles_dir)
        print(f"  Loaded {len(profiles)} profile(s) from {profiles_dir}")

    # Also check the global polywhaler profiles directory for known traders
    global_dir = SCRIPT_DIR / "results" / "polywhaler_profiles"
    if global_dir.is_dir():
        for f in global_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                u = data.get("username")
                if u and u not in profiles:
                    profiles[u] = data
            except (json.JSONDecodeError, OSError):
                pass

    # ── Falcon enrichment for known/returning traders ─────────────────────
    # New traders get Falcon data via run.py. Known traders' cached profiles
    # may predate the Falcon integration — enrich them inline here.
    all_trade_wallets: dict[str, str] = {}
    for t in trades:
        name   = t.get("name", "")
        wallet = t.get("proxyWallet", "")
        if name and wallet and not name.startswith("0x"):
            all_trade_wallets[name] = wallet.lower()

    falcon_token = falcon_analytics.load_token()
    if falcon_token:
        to_enrich = [
            (u, all_trade_wallets[u])
            for u in profiles
            if u in all_trade_wallets and not falcon_analytics.is_fresh(profiles[u])
        ]
        if to_enrich:
            print(f"  Falcon: enriching {len(to_enrich)} returning trader(s)…")

            def _enrich_one(item: tuple[str, str]) -> tuple[str, dict]:
                username, wallet = item
                return username, falcon_analytics.enrich_wallet(wallet, falcon_token)

            with ThreadPoolExecutor(max_workers=4) as pool:
                for username, analytics in pool.map(_enrich_one, to_enrich):
                    if analytics:
                        wallet = all_trade_wallets[username]
                        profiles[username]["polymarket_analytics"] = {"wallet": wallet, **analytics}
                        # Persist so the next run finds it cached.
                        if profiles_dir:
                            slug = re.sub(r"[^a-zA-Z0-9_-]", "_", username)
                            pfile = profiles_dir / f"{slug}.json"
                            if pfile.exists():
                                try:
                                    pfile.write_text(
                                        json.dumps(profiles[username], indent=2, ensure_ascii=False),
                                        encoding="utf-8",
                                    )
                                except OSError:
                                    pass

    # ── Persist all profiles to global cache ────────────────────────────────
    # Ensures returning traders retain OSINT data across dated run directories.
    global_cache_dir = SCRIPT_DIR / "results" / "polywhaler_profiles"
    global_cache_dir.mkdir(parents=True, exist_ok=True)
    for _uname, _profile in profiles.items():
        _slug = re.sub(r"[^a-zA-Z0-9_-]", "_", _uname)
        try:
            (global_cache_dir / f"{_slug}.json").write_text(
                json.dumps(_profile, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            pass
    if profiles:
        print(f"  Global profile cache: wrote {len(profiles)} profile(s) → {global_cache_dir}")

    # ── Score ─────────────────────────────────────────────────────────────
    # Group trades by username so each trader gets one entry (their best trade).
    trades_by_user: dict[str, list[dict]] = {}
    for trade in trades:
        username = trade.get("name")
        if not username or username.startswith("0x"):
            continue
        trades_by_user.setdefault(username, []).append(trade)

    # ── Blocklist filter (scoring stage) ─────────────────────────────────────
    if blocked_wallets or blocked_usernames:
        before = len(trades_by_user)
        trades_by_user = {
            u: ts for u, ts in trades_by_user.items()
            if u.lower() not in blocked_usernames
            and not any(t.get("proxyWallet", "").lower() in blocked_wallets for t in ts)
        }
        skipped_score += before - len(trades_by_user)
        if skipped_score:
            print(f"  Blocklist: suppressed {skipped_score} trader(s) from scoring")

    # ── Sybil clustering ──────────────────────────────────────────────────
    # Build a wallet→cluster_peers map so score_against_market can flag it.
    # Only wallets in the current run's trade list are considered.
    wallet_to_cluster_peers: dict[str, list[str]] = {}
    wallet_to_cluster_aggregate: dict[str, float] = {}
    wallet_to_cluster_funders: dict[str, list[str]] = {}
    if not args.no_sybil and all_trade_wallets:
        run_wallets = [
            w for u, w in all_trade_wallets.items()
            if u in trades_by_user  # only scored traders
        ]
        if len(run_wallets) >= 2:
            clusters, cluster_funders = sybil_clustering.build_clusters(
                run_wallets,
                lookback_days=args.sybil_lookback,
            )
            # Pre-compute best trade size per username for aggregate calculation
            username_best_size: dict[str, float] = {
                u: max(ts, key=lambda t: t.get("insiderScore") or 0).get("size") or 0
                for u, ts in trades_by_user.items()
            }
            w2u = {w: u for u, w in all_trade_wallets.items()}
            # Invert to wallet → other cluster members; compute aggregate per cluster
            for root, members in clusters.items():
                agg = sum(username_best_size.get(w2u.get(m, ""), 0) for m in members)
                funders = cluster_funders.get(root, [])
                for wallet in members:
                    peers = [m for m in members if m != wallet]
                    wallet_to_cluster_peers[wallet] = peers
                    wallet_to_cluster_aggregate[wallet] = agg
                    wallet_to_cluster_funders[wallet] = funders
        else:
            print("  Sybil: fewer than 2 wallets — skipping.")

    results: list[dict] = []
    no_profile_count = 0

    for username, user_trades in trades_by_user.items():
        real_profile = profiles.get(username)
        if not real_profile:
            no_profile_count += 1
            profile = {"username": username, "profiles": [], "sherlock_claimed": []}
        else:
            profile = real_profile

        # Score against the highest-insiderScore trade; surface all market positions.
        best_trade = max(user_trades, key=lambda t: t.get("insiderScore") or 0)
        # osint_ran=True only when a real profile was loaded — enables ghost-account detection.
        result = score_against_market(username, profile, best_trade, osint_ran=real_profile is not None)

        # ── Sybil cluster flag ────────────────────────────────────────────
        wallet = all_trade_wallets.get(username, "").lower()
        peers = wallet_to_cluster_peers.get(wallet, [])
        if peers:
            wallet_to_username = {w: u for u, w in all_trade_wallets.items()}
            peer_names = [wallet_to_username.get(p, p[:10] + "…") for p in peers]
            agg_usd = wallet_to_cluster_aggregate.get(wallet, 0)
            S = scoring.SCORING
            agg_pts = 0
            if agg_usd >= S["sybil_huge_aggregate_usd"]:
                agg_pts = S["sybil_huge_aggregate_pts"]
            elif agg_usd >= S["sybil_large_aggregate_usd"]:
                agg_pts = S["sybil_large_aggregate_pts"]
            total_pts = S["sybil_cluster_pts"] + agg_pts
            result["flags"].append({
                "type": "sybil_cluster",
                "cluster_peers": peer_names,
                "cluster_aggregate_usd": round(agg_usd),
                "shared_funders": wallet_to_cluster_funders.get(wallet, []),
                "points": total_pts,
            })
            result["our_score"] += total_pts

        # Attach all markets this trader bet on (not just the best-scored one).
        result["all_trades"] = [
            {
                "title":         t.get("title", ""),
                "outcome":       t.get("outcome", ""),
                "size":          t.get("size") or 0,
                "insider_score": t.get("insiderScore") or 0,
                "category":      t.get("category", ""),
            }
            for t in sorted(user_trades, key=lambda t: -(t.get("insiderScore") or 0))
        ]
        results.append(result)

    if no_profile_count:
        print(f"  {no_profile_count} trader(s) scored without OSINT profile")

    # ── Penalise pure-polywhaler alerts (applied after all flags including sybil) ──
    # Flags that are NOT independent corroboration of insider status:
    _NON_CORROBORATING = frozenset({
        "polywhaler_insider_score", "large_trade", "medium_trade", "pre_resolution_trade",
    })
    for result in results:
        has_corroboration = any(f["type"] not in _NON_CORROBORATING for f in result["flags"])
        if not has_corroboration and any(f["type"] == "polywhaler_insider_score" for f in result["flags"]):
            penalty = scoring.SCORING["pure_polywhaler_penalty"]
            result["flags"].append({
                "type": "low_confidence",
                "reason": "polywhaler_only",
                "points": penalty,
            })
            result["our_score"] += penalty

    # ── Write outputs ─────────────────────────────────────────────────────
    analysis_file = out_dir / "analysis.json"
    analysis_file.write_text(
        json.dumps(sorted(results, key=lambda x: -x["our_score"]), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n{'='*72}")
    report_file = write_report(results, out_dir, date_str)

    # ── Run stats ─────────────────────────────────────────────────────────
    run_stats = {
        "date":                   date_str,
        "trades_fetched":         len(trades),
        "new_traders":            len(new_usernames),
        "traders_scored":         len(results),
        "blocklisted_skipped_osint":  skipped_osint,
        "blocklisted_skipped_score":  skipped_score,
        "profiles_cached_globally":   len(profiles),
    }
    (out_dir / "run_stats.json").write_text(
        json.dumps(run_stats, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nOutputs → {out_dir}/")
    print(f"  trades.json    {len(trades)} flagged trades")
    print(f"  analysis.json  {len(results)} scored traders")
    print(f"  report.txt     ranked summary")
    print(f"  run_stats.json health metrics")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
