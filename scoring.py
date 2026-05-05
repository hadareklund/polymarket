"""Shared scoring utilities and keyword lists for the polywhaler pipeline.

Imported by both polywhaler_monitor.py and analyze_insider_trading.py so
the firm lists and text-extraction logic stay in sync automatically.
"""
from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# Configurable scoring thresholds — tune here without editing logic
# ---------------------------------------------------------------------------

SCORING: dict = {
    # OSINT signal point values
    "direct_entity_match_linkedin_pts":  20,
    "direct_entity_match_pts":           18,
    "category_keyword_pts":               8,
    "investment_bank_pts":                8,
    "vc_firm_pts":                        6,
    "securities_law_pts":                 6,
    "investment_firm_pts":                5,
    # Trade size thresholds and points
    "large_trade_usd":               100_000,
    "large_trade_pts":                    3,
    "medium_trade_usd":               25_000,
    "medium_trade_pts":                   1,
    # Ghost / no-presence signal
    "no_online_presence_pts":             2,
    # Penalty when the only flag is polywhaler_insider_score
    "pure_polywhaler_penalty":           -3,
    # LinkedIn snippet/company quality filters
    "linkedin_min_company_len":           5,   # chars; shorter extracted company = noise
    "linkedin_min_snippet_len":          20,   # chars; shorter snippet = bare job title
    # Sybil cluster points
    "sybil_cluster_pts":                  3,   # flat membership bonus
    "sybil_large_aggregate_usd":    200_000,   # cluster total ≥ this → extra pts
    "sybil_large_aggregate_pts":          2,
    "sybil_huge_aggregate_usd":     500_000,
    "sybil_huge_aggregate_pts":           3,
    # Polymarket portfolio thresholds (replaces Falcon's unreliable lifetime_performance)
    "polymarket_min_portfolio":     100_000,  # portfolio_value threshold
    "polymarket_portfolio_pts":           2,
    "polymarket_min_top_pos_pct":      0.40,  # top position ≥ 40% of portfolio = concentrated thesis
    "polymarket_concentration_pts":       2,
    # Falcon wallet_360 thresholds and points (win_rate, sharpe, diversity)
    "falcon_min_win_rate":             0.75,
    "falcon_win_rate_pts":                2,
    "falcon_min_sharpe":                2.0,
    "falcon_sharpe_pts":                  2,
    "falcon_max_diversity":             0.3,
    "falcon_min_trades_concentration":   20,
    "falcon_concentration_pts":           1,
    # Kept for backward compat with cached profiles that still have lifetime_performance
    "falcon_min_pnl":                50_000,
    "falcon_pnl_pts":                     2,
    "falcon_min_roi_pct":                15,
    "falcon_min_roi_trades":             50,
    "falcon_roi_pts":                     2,
}

# ---------------------------------------------------------------------------
# Professional site filter
# ---------------------------------------------------------------------------

PROFESSIONAL_SITES: frozenset[str] = frozenset({"GitHub", "Hugging Face", "LinkedIn"})

# ---------------------------------------------------------------------------
# Finance keyword lists  (union of all pipeline sources)
# ---------------------------------------------------------------------------

INVESTMENT_BANKS: list[str] = [
    "goldman sachs", "morgan stanley", "jpmorgan", "jp morgan", "j.p. morgan",
    "bank of america", "merrill lynch", "citigroup", "citibank", "deutsche bank",
    "barclays", "credit suisse", "jefferies", "lazard", "rothschild", "evercore",
    "moelis", "houlihan lokey", "piper sandler", "raymond james",
    "wells fargo securities", "hsbc", "nomura", "macquarie capital",
    "rbc capital markets",
]

VC_FIRMS: list[str] = [
    "sequoia capital", "andreessen horowitz", "a16z", "kleiner perkins",
    "accel partners", "accel ",      # "Accel" standalone in bio context
    "benchmark capital", "greylock partners", "index ventures",
    "tiger global", "softbank", "vision fund", "general catalyst", "founders fund",
    "khosla ventures", "spark capital", "greenoaks capital", "coatue management",
    "insight partners", "bessemer venture", "lightspeed venture", "battery ventures",
    "dragoneer investment", "thrive capital", "redpoint ventures",
    "y combinator", "ycombinator", "first round capital", "felicis ventures",
    "matrix partners", "menlo ventures", "google ventures",
]

SECURITIES_LAW: list[str] = [
    "skadden", "skadden arps",
    "sullivan & cromwell",
    "latham & watkins", "latham watkins",
    "davis polk",
    "cooley llp",
    "wilson sonsini",
    "fenwick & west", "fenwick west",
    "gunderson dettmer",
    "kirkland & ellis",
    "paul weiss",
    "simpson thacher",
    "cleary gottlieb",
    "weil gotshal",
]

# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

_URL_RE      = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
_HTML_TAG    = re.compile(r"<[^>]+>")
_HTML_ENTITY = re.compile(r"&#?\w+;")


def clean_html(text: str) -> str:
    text = _HTML_TAG.sub(" ", text)
    text = _HTML_ENTITY.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()


def kw_match(text: str, keyword: str) -> bool:
    """Word-boundary match after stripping URLs, case-insensitive."""
    clean = _URL_RE.sub(" ", text)
    return bool(re.search(r"\b" + re.escape(keyword.strip()) + r"\b", clean.lower()))


def parse_linkedin_company(title: str) -> str:
    """Extract employer from a LinkedIn search-result title.

    Handles 'Name - Company | LinkedIn' and 'Name - Role - Company | LinkedIn'.
    Returns the last dash-separated segment, which is the current employer.
    Rejects results that are too short to be a real company name (bare job titles).
    """
    m = re.match(r"^(.+?)\s*\|\s*LinkedIn\s*$", title, re.IGNORECASE)
    if not m:
        return ""
    parts = [p.strip() for p in m.group(1).split(" - ")]
    if len(parts) < 2:
        return ""
    company = parts[-1]
    if len(company) < SCORING["linkedin_min_company_len"]:
        return ""
    return company


# ---------------------------------------------------------------------------
# Professional field extraction
# ---------------------------------------------------------------------------

def prof_fields_from_site(site_profile: dict) -> list[tuple[str, str]]:
    """Return (field_label, text) pairs from a single site profile dict.

    Only processes sites in PROFESSIONAL_SITES; returns [] for all others.
    """
    results: list[tuple[str, str]] = []
    site = site_profile.get("site", "")
    if site not in PROFESSIONAL_SITES:
        return results

    if site == "LinkedIn":
        company = parse_linkedin_company(site_profile.get("title", ""))
        if company:
            results.append(("LinkedIn.company", company))
        snippet = clean_html(site_profile.get("snippet", ""))
        # Reject snippets that are too short to contain employer context (bare job titles)
        if snippet and len(snippet) >= SCORING["linkedin_min_snippet_len"]:
            results.append(("LinkedIn.snippet", snippet))
        return results

    for key in ("bio", "company"):
        val = (site_profile.get(key) or "").strip()
        if val:
            results.append((f"{site}.{key}", val))

    if site == "GitHub":
        for org in site_profile.get("organizations", []):
            text = " ".join(filter(None, [
                org.get("login", "") if isinstance(org, dict) else str(org),
                org.get("description", "") if isinstance(org, dict) else "",
            ])).strip()
            if text:
                results.append(("GitHub.org", text))

    return results


def prof_fields_from_profile(user_profile: dict) -> list[tuple[str, str]]:
    """Return (field_label, text) pairs from all professional sites in a user profile."""
    results: list[tuple[str, str]] = []
    for site_profile in user_profile.get("profiles", []):
        results.extend(prof_fields_from_site(site_profile))
    return results


# ---------------------------------------------------------------------------
# Falcon on-chain scoring
# ---------------------------------------------------------------------------

def falcon_flags(profile: dict) -> tuple[list[dict], int]:
    """Score a profile's polymarket_analytics block.

    Uses positions_data (from Polymarket API) for portfolio/size signals, and
    wallet_360_30d (from Falcon) for win_rate, sharpe, and diversity signals.
    Falls back to the legacy lifetime_performance block for cached profiles
    that predate the Polymarket API integration.

    Returns (flags, score) where flags is a list of flag dicts (each with a
    'points' key) and score is the sum of those points.
    """
    analytics = profile.get("polymarket_analytics", {})
    pos   = analytics.get("positions_data", {})
    w360  = analytics.get("wallet_360_30d", {})
    perf  = analytics.get("lifetime_performance", {})  # legacy fallback only

    S = SCORING
    flags: list[dict] = []
    score = 0

    # ── Portfolio size (Polymarket API) ───────────────────────────────────
    portfolio_value = float(pos.get("portfolio_value") or 0)
    if portfolio_value >= S["polymarket_min_portfolio"]:
        flags.append({
            "type":            "large_portfolio",
            "portfolio_value": round(portfolio_value),
            "points":          S["polymarket_portfolio_pts"],
        })
        score += S["polymarket_portfolio_pts"]

    # Concentrated single-thesis bet (top position ≥ threshold % of portfolio)
    top_pct   = float(pos.get("top_position_pct")   or 0)
    top_title = pos.get("top_position_title", "")
    top_value = float(pos.get("top_position_value") or 0)
    if portfolio_value >= S["polymarket_min_portfolio"] and top_pct >= S["polymarket_min_top_pos_pct"]:
        flags.append({
            "type":        "concentrated_thesis",
            "top_pct":     round(top_pct, 2),
            "top_value":   round(top_value),
            "top_title":   top_title[:80],
            "points":      S["polymarket_concentration_pts"],
        })
        score += S["polymarket_concentration_pts"]

    # ── Legacy fallback: cached profiles without positions_data ──────────
    if not pos and perf:
        try:
            total_pnl = float(perf.get("total_pnl") or 0)
            roi_pct   = float(perf.get("roi_pct")   or 0)
            n_trades  = int(perf.get("total_trades") or 0)
        except (ValueError, TypeError):
            total_pnl = roi_pct = n_trades = 0
        if total_pnl >= S["falcon_min_pnl"]:
            flags.append({"type": "falcon_large_pnl", "total_pnl": round(total_pnl),
                          "points": S["falcon_pnl_pts"], "note": "legacy-data"})
            score += S["falcon_pnl_pts"]
        if roi_pct >= S["falcon_min_roi_pct"] and n_trades >= S["falcon_min_roi_trades"]:
            flags.append({"type": "falcon_high_roi", "roi_pct": round(roi_pct, 1),
                          "total_trades": n_trades, "points": S["falcon_roi_pts"], "note": "legacy-data"})
            score += S["falcon_roi_pts"]

    # ── Falcon wallet_360 (win_rate, sharpe, diversity) ───────────────────
    try:
        win_rate  = float(w360.get("win_rate")                 or 0)
        sharpe    = float(w360.get("sharpe_ratio")             or 0)
        diversity = float(w360.get("category_diversity_score") or 1)
        n_trades  = int(w360.get("total_trades")               or 0)
    except (ValueError, TypeError):
        win_rate = sharpe = 0; diversity = 1; n_trades = 0

    window_days = w360.get("window_days")
    if win_rate >= S["falcon_min_win_rate"]:
        flags.append({"type": "falcon_high_win_rate", "win_rate": round(win_rate, 3),
                      "window_days": window_days, "points": S["falcon_win_rate_pts"]})
        score += S["falcon_win_rate_pts"]
    if sharpe >= S["falcon_min_sharpe"]:
        flags.append({"type": "falcon_high_sharpe", "sharpe_ratio": round(sharpe, 2),
                      "window_days": window_days, "points": S["falcon_sharpe_pts"]})
        score += S["falcon_sharpe_pts"]
    if diversity < S["falcon_max_diversity"] and n_trades >= S["falcon_min_trades_concentration"]:
        flags.append({"type": "falcon_concentrated_bets", "diversity_score": round(diversity, 2),
                      "window_days": window_days, "points": S["falcon_concentration_pts"]})
        score += S["falcon_concentration_pts"]

    return flags, score
