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
    # Falcon agent 569: realized PnL from settled markets (authoritative accuracy signal)
    # Note: agent 569 win_rate = wins/total_trades (open included), so rates are low (5–40%).
    # Low win_rate + high PnL is actually MORE suspicious (large conviction bets).
    # win_rate flag removed — use wallet_360 rolling win_rate instead.
    "falcon_min_realized_pnl":       50_000,
    "falcon_realized_pnl_pts":            2,
    # Polymarket portfolio (current sophistication/scale signal)
    "polymarket_min_portfolio":     100_000,
    "polymarket_portfolio_pts":           2,
    "polymarket_min_top_pos_pct":      0.40,  # top position ≥ 40% = concentrated thesis
    "polymarket_concentration_pts":       2,
    # Falcon wallet_360 thresholds and points (win_rate, sharpe, diversity, sybil)
    "falcon_min_win_rate":             0.75,
    "falcon_win_rate_pts":                2,
    "falcon_min_sharpe":                2.0,
    "falcon_sharpe_pts":                  2,
    "falcon_max_diversity":             0.3,
    "falcon_min_trades_concentration":   20,
    "falcon_concentration_pts":           1,
    "falcon_min_sybil_risk":            0.7,  # sybil_risk_score ≥ this = flag
    "falcon_sybil_risk_pts":              2,
    # Kept for backward compat with cached profiles that still have lifetime_performance
    "falcon_min_pnl":                50_000,
    "falcon_pnl_pts":                     2,
    "falcon_min_roi_pct":                15,
    "falcon_min_roi_trades":             50,
    "falcon_roi_pts":                     2,
    # Fix 1+3: role domain → market subject relevance
    # Awarded when a trader's professional role (parsed from LinkedIn) maps to the
    # specific subject matter of the market they bet on (e.g. marine cargo → Iran/Hormuz).
    "role_domain_match_pts":          12,
    # Fix 2: thematic bet clustering — annotation only, no scoring points.
    # Multiple bets on related markets is equally consistent with following the
    # news as with having insider access, so we surface the cluster in the report
    # for analyst context but do not award score for it.
    "thematic_cluster_min_usd":   25_000,   # per-trade minimum to count in a cluster
    # Fix 4: identity corroboration
    # Bonus when ≥2 professional platforms (GitHub, HuggingFace, LinkedIn) agree on
    # the same real name; penalty when they disagree.
    "identity_corroborated_bonus":     3,
    "identity_fragmented_penalty":    -3,
    # Bot / market-maker detection — strongly negative signals.
    # A genuine insider makes a small number of large targeted bets.
    # Automated market-makers trade hundreds of times per day across every
    # category with sub-$1k sizes; that pattern disqualifies insider attribution.
    "bot_trades_per_day_strong":     100,   # ≥ this trades/day in rolling window
    "bot_trades_per_day_moderate":    30,   # ≥ this trades/day
    "bot_strong_pts":                  -6,
    "bot_moderate_pts":                -2,
    "bot_min_lifetime_trades":      1_000,  # need volume before judging win rate
    "bot_max_lifetime_win_rate":     0.48,  # <this = not picking direction, making spread
    "bot_market_maker_pts":            -4,
    "bot_min_open_positions":           20,  # spread across too many markets
    "bot_max_avg_position_usd":      5_000,  # tiny average size per position
    "bot_dispersion_pts":              -2,
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
# Industry vertical → market domain mapping  (Fix 1 + Fix 3)
#
# role_keywords:   terms found in a LinkedIn title/snippet that identify the
#                  trader's professional domain.
# market_keywords: terms in a Polymarket market title that indicate the market
#                  is relevant to that domain.
# label:           human-readable vertical name used in flag output.
#
# Scoring: if ≥1 role_keyword matches the trader's profile AND ≥1 market_keyword
# matches the market title, award role_domain_match_pts.  The vertical with the
# most matched role_keywords wins (prevents double-counting).
# ---------------------------------------------------------------------------

INDUSTRY_VERTICAL_DOMAINS: dict[str, dict] = {
    "marine_cargo_shipping": {
        "role_keywords": [
            "marine", "cargo", "shipping", "freight", "logistics", "maritime",
            "vessel", "port", "tanker", "container", "fleet", "supply chain",
        ],
        "market_keywords": [
            "hormuz", "iran", "suez", "strait", "shipping", "cargo", "maritime",
            "vessel", "port", "tanker", "blockade", "naval", "sea lane",
        ],
        "label": "Marine/Cargo/Shipping",
    },
    "defense_aerospace": {
        "role_keywords": [
            "defense", "defence", "aerospace", "military", "air force", "army",
            "navy", "pentagon", "nato", "weapons", "airspace", "aviation security",
            "combat", "missile", "surveillance", "national security",
        ],
        "market_keywords": [
            "military", "conflict", "war", "airspace", "aircraft", "missile",
            "nato", "defense", "defence", "strike", "troops", "invasion",
            "ceasefire", "drone",
        ],
        "label": "Defense/Aerospace",
    },
    "energy_commodities": {
        "role_keywords": [
            "oil", "gas", "energy", "petroleum", "opec", "pipeline", "refinery",
            "commodity", "commodities", "natural gas", "lng", "oil and gas",
            "upstream", "downstream", "hydrocarbon",
        ],
        "market_keywords": [
            "oil", "opec", "pipeline", "energy", "gas", "barrel", "brent",
            "wti", "crude", "lng", "natural gas", "production cut", "oil price",
        ],
        "label": "Energy/Commodities",
    },
    "pharma_biotech": {
        "role_keywords": [
            "pharmaceutical", "pharma", "biotech", "drug", "clinical",
            "therapeutics", "oncology", "genomics", "biopharma", "medical device",
            "life sciences", "clinical trial", "regulatory affairs",
        ],
        "market_keywords": [
            "fda", "drug", "approval", "clinical", "trial", "pharma",
            "biotech", "treatment", "nda", "anda", "pdufa", "ema",
        ],
        "label": "Pharma/Biotech",
    },
    "financial_regulation": {
        "role_keywords": [
            "regulatory", "compliance", "finra", "regulator",
            "oversight", "enforcement", "financial regulation",
            "prudential", "monetary policy", "central bank", "federal reserve",
            "treasury", "financial stability",
        ],
        "market_keywords": [
            "sec", "regulation", "fed", "fomc", "rate hike", "rate cut",
            "interest rate", "enforcement", "monetary", "central bank",
            "fed chair", "treasury secretary",
        ],
        "label": "Financial Regulation",
    },
    "intelligence_geopolitical": {
        "role_keywords": [
            "geopolitical", "political risk", "country risk",
            "intelligence", "foreign policy", "national security",
            "strategic affairs", "risk advisory", "diplomatic",
            "state department", "foreign service",
        ],
        "market_keywords": [
            "sanctions", "iran", "russia", "china", "north korea",
            "diplomatic", "nuclear", "treaty", "ceasefire", "summit",
            "negotiations", "embassy",
        ],
        "label": "Intelligence/Geopolitical Risk",
    },
    "tech_semiconductor": {
        "role_keywords": [
            "semiconductor", "chip", "foundry", "chip design",
            "advanced manufacturing", "fab", "wafer", "silicon",
            "export control", "integrated circuit",
        ],
        "market_keywords": [
            "chip", "semiconductor", "export", "tsmc", "nvidia",
            "ai chip", "export control", "advanced computing", "foundry",
        ],
        "label": "Tech/Semiconductors",
    },
    "real_estate_construction": {
        "role_keywords": [
            "real estate", "property", "mortgage", "housing", "construction",
            "realty", "reit", "commercial real estate", "residential",
        ],
        "market_keywords": [
            "housing", "mortgage", "home price", "real estate", "reit",
            "housing market", "construction", "home sales",
        ],
        "label": "Real Estate/Construction",
    },
}

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
    rp    = analytics.get("realized_performance", {})   # agent 569 — net realized PnL
    pos   = analytics.get("positions_data", {})          # Polymarket API — current portfolio
    w360  = analytics.get("wallet_360_30d", {})          # agent 581 — behavioral/risk
    perf  = analytics.get("lifetime_performance", {})    # legacy agent 586 — fallback only

    S = SCORING
    flags: list[dict] = []
    score = 0

    # ── Realized PnL (Falcon agent 569 — net settled-market gains) ────────
    try:
        realized = float(rp.get("pnl")      or 0)
        r_trades = int(rp.get("trades")     or 0)
        r_wins   = int(rp.get("wins")       or 0)
        r_losses = int(rp.get("losses")     or 0)
        r_wr     = float(rp.get("win_rate") or 0)
    except (ValueError, TypeError):
        realized = r_trades = r_wins = r_losses = 0; r_wr = 0.0

    if realized >= S["falcon_min_realized_pnl"]:
        flags.append({
            "type":         "falcon_realized_pnl",
            "realized_pnl": round(realized),
            "trades":       r_trades,
            "wins":         r_wins,
            "losses":       r_losses,
            "points":       S["falcon_realized_pnl_pts"],
        })
        score += S["falcon_realized_pnl_pts"]

    # ── Portfolio size (Polymarket API — current scale/sophistication) ────
    portfolio_value = float(pos.get("portfolio_value") or 0)
    if portfolio_value >= S["polymarket_min_portfolio"]:
        flags.append({
            "type":            "large_portfolio",
            "portfolio_value": round(portfolio_value),
            "points":          S["polymarket_portfolio_pts"],
        })
        score += S["polymarket_portfolio_pts"]

    # Concentrated thesis: top position ≥ threshold % of a large portfolio
    top_pct   = float(pos.get("top_position_pct")   or 0)
    top_title = pos.get("top_position_title", "")
    top_value = float(pos.get("top_position_value") or 0)
    if portfolio_value >= S["polymarket_min_portfolio"] and top_pct >= S["polymarket_min_top_pos_pct"]:
        flags.append({
            "type":      "concentrated_thesis",
            "top_pct":   round(top_pct, 2),
            "top_value": round(top_value),
            "top_title": top_title[:80],
            "points":    S["polymarket_concentration_pts"],
        })
        score += S["polymarket_concentration_pts"]

    # ── Falcon wallet_360 (sharpe, diversity, sybil_risk) ─────────────────
    try:
        win_rate     = float(w360.get("win_rate")                 or 0)
        sharpe       = float(w360.get("sharpe_ratio")             or 0)
        diversity    = float(w360.get("category_diversity_score") or 1)
        n_trades     = int(w360.get("total_trades")               or 0)
        sybil_risk   = float(w360.get("sybil_risk_score")         or 0)
    except (ValueError, TypeError):
        win_rate = sharpe = sybil_risk = 0; diversity = 1; n_trades = 0

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
    if sybil_risk >= S["falcon_min_sybil_risk"]:
        flags.append({"type": "falcon_sybil_risk", "sybil_risk_score": round(sybil_risk, 3),
                      "risk_level": w360.get("risk_level", ""),
                      "points": S["falcon_sybil_risk_pts"]})
        score += S["falcon_sybil_risk_pts"]

    # ── Bot / market-maker detection ──────────────────────────────────────
    # Automated market-makers and bots are the opposite of insiders: they trade
    # constantly across every category at tiny sizes, earning on bid-ask spread
    # rather than informational edge.  Each signal below is negative evidence
    # for insider status and carries a score penalty.

    # High-frequency: trades/day in the rolling window
    if n_trades > 0 and window_days:
        try:
            wd = int(window_days)
        except (ValueError, TypeError):
            wd = 0
        if wd > 0:
            tpd = n_trades / wd
            if tpd >= S["bot_trades_per_day_strong"]:
                flags.append({
                    "type":           "high_frequency_trader",
                    "trades_per_day": round(tpd, 1),
                    "window_days":    window_days,
                    "points":         S["bot_strong_pts"],
                })
                score += S["bot_strong_pts"]
            elif tpd >= S["bot_trades_per_day_moderate"]:
                flags.append({
                    "type":           "high_frequency_trader",
                    "trades_per_day": round(tpd, 1),
                    "window_days":    window_days,
                    "points":         S["bot_moderate_pts"],
                })
                score += S["bot_moderate_pts"]

    # Lifetime market-maker pattern: high volume + below-50% directional win rate.
    # Insiders win directionally; market-makers don't need to.
    if r_trades >= S["bot_min_lifetime_trades"] and 0 < r_wr < S["bot_max_lifetime_win_rate"]:
        flags.append({
            "type":            "market_maker_pattern",
            "lifetime_trades": r_trades,
            "win_rate":        round(r_wr, 4),
            "points":          S["bot_market_maker_pts"],
        })
        score += S["bot_market_maker_pts"]

    # Over-dispersed portfolio: many small open positions across unrelated markets.
    # Insiders concentrate; bots spray.
    open_pos = int(pos.get("open_positions") or 0)
    if open_pos >= S["bot_min_open_positions"] and portfolio_value > 0:
        avg_pos_usd = portfolio_value / open_pos
        if avg_pos_usd < S["bot_max_avg_position_usd"]:
            flags.append({
                "type":             "dispersed_portfolio",
                "open_positions":   open_pos,
                "avg_position_usd": round(avg_pos_usd),
                "points":           S["bot_dispersion_pts"],
            })
            score += S["bot_dispersion_pts"]

    # ── Legacy fallback: cached profiles with only lifetime_performance ───
    if not rp and not pos and perf:
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

    return flags, score


# ---------------------------------------------------------------------------
# Fix 3: LinkedIn role depth parsing
# ---------------------------------------------------------------------------

def parse_linkedin_role_text(title: str) -> str:
    """Extract the role/title segments from a LinkedIn search-result title.

    LinkedIn titles follow the pattern:
        'Name - Role | LinkedIn'
        'Name - Role - Company | LinkedIn'
        'Name - Title1 - Title2 - Company | LinkedIn'

    Returns everything between the name (first segment) and the company (last
    segment), i.e. the actual job title(s).  Returns '' when there are fewer
    than 3 dash-separated segments (not enough to have a distinct role middle).

    Example:
        'Thiago Gonçalves - Managing Director - Head of Marine & Cargo - Marsh | LinkedIn'
        → 'Managing Director - Head of Marine & Cargo'
    """
    m = re.match(r"^(.+?)\s*\|\s*LinkedIn\s*$", title, re.IGNORECASE)
    if not m:
        return ""
    parts = [p.strip() for p in m.group(1).split(" - ")]
    if len(parts) < 3:
        return ""
    return " - ".join(parts[1:-1])


# ---------------------------------------------------------------------------
# Fix 1+3: Industry vertical detection and market-domain matching
# ---------------------------------------------------------------------------

def detect_role_domain(profile: dict) -> tuple[str, list[str], str] | None:
    """Identify the trader's industry vertical from their LinkedIn role and snippet.

    Searches the role text (middle segments of the LinkedIn title) plus the
    LinkedIn snippet for terms defined in INDUSTRY_VERTICAL_DOMAINS.  Returns
    the best-matching vertical as (vertical_key, matched_role_keywords, label),
    or None if nothing matches.

    'Best' is defined as the vertical with the most matched role_keywords,
    with ties broken by label order.
    """
    text_parts: list[str] = []
    for p in profile.get("profiles", []):
        if p.get("site") != "LinkedIn":
            continue
        role = parse_linkedin_role_text(p.get("title", ""))
        if role:
            text_parts.append(role.lower())
        snippet = clean_html(p.get("snippet", ""))
        if snippet:
            text_parts.append(snippet.lower())

    if not text_parts:
        return None

    combined = " ".join(text_parts)

    best_key: str | None = None
    best_matched: list[str] = []

    for key, vdata in INDUSTRY_VERTICAL_DOMAINS.items():
        matched = [kw for kw in vdata["role_keywords"] if kw in combined]
        if len(matched) > len(best_matched):
            best_key = key
            best_matched = matched

    if not best_key:
        return None

    return best_key, best_matched, INDUSTRY_VERTICAL_DOMAINS[best_key]["label"]


# ---------------------------------------------------------------------------
# Fix 4: Identity corroboration across professional platforms
# ---------------------------------------------------------------------------

# LinkedIn is excluded here because it is ALWAYS found by searching a name
# derived from another platform (see linkedin_batch.py).  Counting LinkedIn
# and its name-source as two agreeing platforms is circular — they agree by
# construction.  Only username-scraped platforms (found independently via
# Sherlock + per-site scripts) can provide genuine corroboration.
_PROFESSIONAL_NAME_SITES: frozenset[str] = frozenset({"GitHub", "Hugging Face"})


def _extract_professional_name(site_profile: dict) -> str | None:
    """Extract a candidate real name from a professional-platform profile dict.

    Returns the name lowercased, or None if no usable name is found.
    Only considers names with ≥2 parts and ≥4 chars total (filters aliases).
    """
    site = site_profile.get("site", "")
    raw  = ""
    if site == "LinkedIn":
        title = site_profile.get("title", "")
        if " | LinkedIn" in title:
            inner = title.split(" | LinkedIn")[0]
            raw   = inner.split(" - ")[0].strip() if " - " in inner else inner.strip()
    elif site == "Hugging Face":
        raw = (site_profile.get("full_name") or "").strip()
    elif site == "GitHub":
        raw = (site_profile.get("name") or "").strip()

    if not raw or len(raw) < 4:
        return None
    parts = raw.split()
    if len(parts) < 2:
        return None
    if any(p.isdigit() for p in parts):
        return None
    return raw.lower()


def identity_corroboration(profile: dict) -> tuple[int, str]:
    """Check whether professional platforms agree on the trader's real identity.

    Examines GitHub, HuggingFace, and LinkedIn for real names.  Returns
    (score_adjustment, reason_string):

    • +identity_corroborated_bonus  when ≥2 sites agree on the same name
      (or share a last name, handling abbreviated forms like 'T. Gonçalves').
    • identity_fragmented_penalty   when ≥2 sites give clearly different names.
    • 0                             when there is only one data point.

    The adjustment is applied on top of the LinkedIn-derived entity/domain
    scores, so a strongly corroborated identity earns a larger bonus while
    a fragmented one is discounted.
    """
    names_by_site: dict[str, str] = {}
    for p in profile.get("profiles", []):
        if p.get("site") not in _PROFESSIONAL_NAME_SITES:
            continue
        name = _extract_professional_name(p)
        if name:
            names_by_site[p["site"]] = name

    if len(names_by_site) < 2:
        return 0, ""

    names  = list(names_by_site.values())
    unique = set(names)

    if len(unique) == 1:
        sites = " + ".join(names_by_site)
        return (
            SCORING["identity_corroborated_bonus"],
            f"{sites} all agree: '{names[0]}'",
        )

    # Treat as corroborated if every name shares the same last name token
    # (handles 'thiago gonçalves' vs 'T. Gonçalves' edge cases)
    last_names = {n.split()[-1] for n in names}
    if len(last_names) == 1:
        sites = " + ".join(names_by_site)
        return (
            SCORING["identity_corroborated_bonus"],
            f"{sites} share last name '{last_names.pop()}'",
        )

    # Professional sites disagree on the name — lower confidence in identity link
    conflict = "; ".join(f"{s}='{n}'" for s, n in names_by_site.items())
    return SCORING["identity_fragmented_penalty"], f"conflicting names: {conflict}"
