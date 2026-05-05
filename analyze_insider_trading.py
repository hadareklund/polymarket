#!/usr/bin/env python3
"""
Insider trading detector for Polymarket IPO markets.

Scores each user by cross-referencing their social profiles against:
  1. Direct company affiliation (works at a company whose IPO they bet on)
     - Only fires on professional-context fields: GitHub company/bio/orgs, HuggingFace bio
  2. Finance infrastructure (investment banks, VC firms, securities law firms)
  3. Corporate email domains in commit history
  4. Bet concentration (few high-conviction YES bets vs diversified portfolio)

Output: results/insider_trading_scores.json  +  a ranked console summary
"""

import json
import glob
import re
import os
import sys

import scoring

# Slug can be overridden via first CLI arg: python3 analyze_insider_trading.py <slug>
_SLUG = sys.argv[1] if len(sys.argv) > 1 else "ipos-before-2027"

RESULTS_DIR    = f"results/{_SLUG}_full_holder_usernames"
POSITIONS_FILE = f"results/{_SLUG}_market_positions.json"
OUTPUT_DIR     = f"results/{_SLUG}_analysis"
OUTPUT_FILE    = f"{OUTPUT_DIR}/insider_trading_scores.json"

# ---------------------------------------------------------------------------
# Market slug → keyword aliases to search in professional fields
# ---------------------------------------------------------------------------
COMPANY_KEYWORDS = {
    "discord-ipo-before-2027":          ["discord"],
    "anthropic-ipo-before-2027":        ["anthropic"],
    "openai-ipo-before-2027":           ["openai", "open ai"],
    "stripe-ipo-before-2027":           ["stripe"],
    "databricks-ipo-before-2027":       ["databricks"],
    "anduril-industries-ipo-before-2027": ["anduril"],
    "anduril-ipo-before-2027":          ["anduril"],
    "anysphere-cursor-ipo-before-2027": ["anysphere", "cursor"],
    "applied-intuition-ipo-before-2027":["applied intuition"],
    "brex-ipo-before-2027":             ["brex"],
    "bytedance-ipo-before-2027":        ["bytedance", "byte dance", "tiktok", "tiktok.com"],
    "canva-ipo-before-2027":            ["canva"],
    "celonis-ipo-before-2027":          ["celonis"],
    "cerebras-ipo-before-2027":         ["cerebras"],
    "deel-ipo-before-2027":             ["deel"],
    "epic-games-ipo-before-2027":       ["epic games", "epicgames"],
    "fannie-mae-ipo-before-2027":       ["fannie mae", "fanniemae", "fnma"],
    "freddie-mac-ipo-before-2027":      ["freddie mac", "freddiemac", "fhlmc"],
    "glean-ipo-before-2027":            ["glean"],
    "ledger-ipo-before-2027":           ["ledger"],
    "mistral-ai-ipo-before-2027":       ["mistral"],
    "once-upon-a-farm-ipo-before-2027": ["once upon a farm"],
    "ramp-ipo-before-2027":             ["ramp.com", "@ramp"],
    "remote-ipo-before-2027":           ["remote.com", "@remote"],
    "revolut-ipo-before-2027":          ["revolut"],
    "ripple-labs-ipo-before-2027":      ["ripple labs", "ripplenet"],
    "rippling-ipo-before-2027":         ["rippling"],
    "shein-ipo-before-2027":            ["shein"],
    "spacex-space-exploration-technologies-corp-ipo-before-2027": ["spacex", "space exploration technologies"],
    "vanta-ipo-before-2027":            ["vanta"],
    "waymo-ipo-before-2027":            ["waymo"],
    "wealthfront-ipo-before-2027":      ["wealthfront"],
    "whoop-ipo-before-2027":            ["whoop"],
    "xai-ipo-before-2027":              ["xai", "x.ai"],
}

COMPANY_EMAIL_DOMAINS = {
    "discord-ipo-before-2027":          ["discord.com"],
    "anthropic-ipo-before-2027":        ["anthropic.com"],
    "openai-ipo-before-2027":           ["openai.com"],
    "stripe-ipo-before-2027":           ["stripe.com"],
    "databricks-ipo-before-2027":       ["databricks.com"],
    "anduril-industries-ipo-before-2027":["anduril.com"],
    "anduril-ipo-before-2027":          ["anduril.com"],
    "anysphere-cursor-ipo-before-2027": ["anysphere.inc", "cursor.sh"],
    "applied-intuition-ipo-before-2027":["appliedintuition.com"],
    "brex-ipo-before-2027":             ["brex.com"],
    "bytedance-ipo-before-2027":        ["bytedance.com", "tiktok.com"],
    "canva-ipo-before-2027":            ["canva.com"],
    "celonis-ipo-before-2027":          ["celonis.com"],
    "cerebras-ipo-before-2027":         ["cerebras.net"],
    "deel-ipo-before-2027":             ["deel.com"],
    "epic-games-ipo-before-2027":       ["epicgames.com"],
    "glean-ipo-before-2027":            ["glean.com"],
    "mistral-ai-ipo-before-2027":       ["mistral.ai"],
    "ramp-ipo-before-2027":             ["ramp.com"],
    "remote-ipo-before-2027":           ["remote.com"],
    "revolut-ipo-before-2027":          ["revolut.com"],
    "ripple-labs-ipo-before-2027":      ["ripple.com"],
    "rippling-ipo-before-2027":         ["rippling.com"],
    "shein-ipo-before-2027":            ["shein.com"],
    "spacex-space-exploration-technologies-corp-ipo-before-2027": ["spacex.com"],
    "vanta-ipo-before-2027":            ["vanta.com"],
    "waymo-ipo-before-2027":            ["waymo.com"],
    "wealthfront-ipo-before-2027":      ["wealthfront.com"],
    "whoop-ipo-before-2027":            ["whoop.com"],
    "xai-ipo-before-2027":              ["x.ai"],
}

# Finance lists live in scoring.py (shared with polywhaler_monitor.py).
INVESTMENT_BANKS   = scoring.INVESTMENT_BANKS
VC_FIRMS           = scoring.VC_FIRMS
SECURITIES_LAW_FIRMS = scoring.SECURITIES_LAW

BIG4_ACCOUNTING = [
    "pricewaterhousecoopers",
    "pwc ",
    "deloitte",
    "ernst & young",
    "ernst and young",
    "kpmg",
]

# Big tech employees have deep knowledge of startup/IPO ecosystem through
# direct partnerships, M&A exposure, and insider networks.
BIG_TECH = [
    "google",
    "alphabet",
    "microsoft",
    "meta ",
    "facebook",
    "amazon",
    "apple",
    "nvidia",
    "openai",      # employees betting on competitors
    "anthropic",
    "bytedance",
    "tencent",
    "alibaba",
    "meituan",
    "pdd",         # PDD Holdings / Pinduoduo / Temu
    "salesforce",
    "stripe",
    "square",
    "block inc",
    "a16z",
    "waymo",       # Waymo employees betting on Waymo IPO
]

# Pattern: generic investment firm signals in company field
# (catch "BridgeLake Capital", "Tiger Capital", "Acme Ventures", etc.)
_INVESTMENT_FIRM_RE = re.compile(
    r'\b(capital|ventures?|fund|hedge fund|asset management|investment|trading firm|'
    r'private equity|growth equity|family office)\b',
    re.IGNORECASE,
)

FINANCIAL_HUB_CITIES = [
    "new york", "san francisco", "london", "hong kong", "singapore",
    "chicago", "boston", "palo alto", "menlo park", "san jose",
    "seattle", "los angeles", "zurich", "frankfurt",
]
FINANCIAL_HUB_COUNTRIES = {"us", "gb", "sg", "hk", "de", "ch"}


# ---------------------------------------------------------------------------
# Field extraction — separate professional from general context
# ---------------------------------------------------------------------------

# Sites whose bio/company fields are reliable indicators of professional identity.
# Social/hobby sites (AniList, SoundCloud, Tumblr, etc.) are excluded — their
# bios mention Discord servers, canvas art, Vantage churches, etc.
PROFESSIONAL_SITES = scoring.PROFESSIONAL_SITES


def emails_from_profile(profile: dict) -> list[str]:
    emails = []
    if profile.get("email"):
        emails.append(profile["email"])
    for e in profile.get("commit_emails", []):
        emails.append(e)
    return [e.lower() for e in emails if e and "@" in e]


def location_from_profile(profile: dict) -> str:
    for key in ("location", "country"):
        val = profile.get(key)
        if val:
            text = str(val).strip()
            # Reject long strings — these are biography fields misnamed as location
            if len(text) <= 100:
                return text.lower()
    return ""


def country_code_from_profile(profile: dict) -> str:
    return (profile.get("country_code") or "").lower()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

matches_keyword = scoring.kw_match


def score_user(username: str, profile_data: dict, positions: dict) -> dict:
    user_positions = positions.get(username, {})

    # Build professional text corpus with field labels for auditability
    prof_fields: list[tuple[str, str]] = []
    all_emails: list[str] = []
    all_locations: list[str] = []
    all_country_codes: list[str] = []

    for p in profile_data.get("profiles", []):
        prof_fields.extend(scoring.prof_fields_from_site(p))
        all_emails.extend(emails_from_profile(p))
        loc = location_from_profile(p)
        if loc:
            all_locations.append(loc)
        cc = country_code_from_profile(p)
        if cc:
            all_country_codes.append(cc)

    combined_prof = " ".join(v for _, v in prof_fields).lower()

    flags = []
    score = 0

    # ------------------------------------------------------------------
    # 1. Direct company affiliation (only professional fields)
    # Track which company values already fired to prevent double-counting
    # across similar slugs (e.g. anduril-ipo vs anduril-industries-ipo).
    # ------------------------------------------------------------------
    _matched_company_values: set[str] = set()
    for slug, keywords in COMPANY_KEYWORDS.items():
        mkt = user_positions.get(slug, {})
        for kw in keywords:
            matching_fields = [
                (field, val) for field, val in prof_fields
                if matches_keyword(val, kw)
            ]
            if not matching_fields:
                continue
            yes = mkt.get("yes", False)
            no = mkt.get("no", False)
            best_field = matching_fields[0][0]
            best_val = matching_fields[0][1]
            dedup_key = (best_field, best_val.lower()[:60])
            if dedup_key in _matched_company_values:
                break  # same company value already scored for a prior slug
            _matched_company_values.add(dedup_key)
            context = best_field + ": " + best_val[:80]
            # LinkedIn.company is the most explicit professional source; score higher.
            # LinkedIn.snippet is search-result text; treat like a bio (same as GitHub).
            via_linkedin_company = best_field == "LinkedIn.company"
            if yes or no:
                direction = "YES" if yes else "NO"
                points = 22 if via_linkedin_company else 20
                flags.append({
                    "type": "direct_company_affiliation_linkedin" if via_linkedin_company else "direct_company_affiliation",
                    "market": slug,
                    "keyword": kw,
                    "position": direction,
                    "context": context,
                    "points": points,
                })
                score += points
            else:
                points = 6 if via_linkedin_company else 5
                flags.append({
                    "type": "company_affiliation_no_position",
                    "market": slug,
                    "keyword": kw,
                    "context": context,
                    "points": points,
                })
                score += points
            break  # one match per slug

    # ------------------------------------------------------------------
    # 2. Corporate email domain match
    # ------------------------------------------------------------------
    for slug, domains in COMPANY_EMAIL_DOMAINS.items():
        mkt = user_positions.get(slug, {})
        for domain in domains:
            for email in all_emails:
                if email.endswith("@" + domain):
                    yes = mkt.get("yes", False)
                    no = mkt.get("no", False)
                    direction = "YES" if yes else ("NO" if no else "none")
                    points = 30 if (yes or no) else 10
                    flags.append({
                        "type": "corporate_email_domain",
                        "market": slug,
                        "email": email,
                        "position": direction,
                        "points": points,
                    })
                    score += points

    # ------------------------------------------------------------------
    # 3. Finance infrastructure (professional fields only, full names)
    # LinkedIn.snippet is noisy search-result text — excluded here to avoid
    # false positives from companies mentioned in feed posts or suggestions.
    # ------------------------------------------------------------------
    _finance_fields = [(f, v) for f, v in prof_fields if f != "LinkedIn.snippet"]

    def check_finance_keywords(kw_list: list[str], category: str, base_points: int):
        nonlocal score
        matched_with_context = []
        for kw in kw_list:
            hits = [(field, val) for field, val in _finance_fields if matches_keyword(val, kw)]
            if hits:
                ctx = hits[0][0] + ": " + hits[0][1][:80]
                matched_with_context.append((kw, ctx))
        if matched_with_context:
            flags.append({
                "type": category,
                "matched": [m[0] for m in matched_with_context[:2]],
                "context": matched_with_context[0][1],
                "market_positions": len(user_positions),
                "points": base_points,
            })
            score += base_points

    check_finance_keywords(INVESTMENT_BANKS, "investment_bank", scoring.SCORING["investment_bank_pts"])
    check_finance_keywords(VC_FIRMS, "vc_firm", scoring.SCORING["vc_firm_pts"])
    check_finance_keywords(SECURITIES_LAW_FIRMS, "securities_law_firm", scoring.SCORING["securities_law_pts"])
    check_finance_keywords(BIG4_ACCOUNTING, "big4_accounting", 4)
    check_finance_keywords(BIG_TECH, "big_tech_employee", 4)

    # ------------------------------------------------------------------
    # 3b. Generic investment firm pattern in company field only
    # CamelCase names (BridgeLakeCapital) need substring search, not \b regex.
    # Retail/consumer brands that happen to contain "Capital/Fund/Partners"
    # are excluded — they have no IPO deal-flow access.
    # ------------------------------------------------------------------
    _INV_TERMS = ("capital", "venture", "fund", "hedge", "asset management",
                  "investment", "trading firm", "private equity", "growth equity",
                  "family office", "partners")
    _INV_FIRM_EXCLUSIONS = {
        # Retail banks / consumer brands — not investment entities
        "capital one", "first capital", "capital group", "capital farm credit",
        "capital city", "capital health", "capital university", "capital district",
        "fund for", "partners in", "partners for", "community partners",
        "head of", "director of", "vp of",   # job titles misread as company names
    }
    company_texts = [(f, v) for f, v in prof_fields if f.endswith(".company")]
    for field, val in company_texts:
        val_lower = val.lower()
        if any(excl in val_lower for excl in _INV_FIRM_EXCLUSIONS):
            continue
        matched_term = next((t for t in _INV_TERMS if t in val_lower), None)
        if matched_term:
            flags.append({
                "type": "investment_firm_company",
                "company": val,
                "matched_term": matched_term,
                "market_positions": len(user_positions),
                "points": scoring.SCORING["investment_firm_pts"],
                "context": f"{field}: {val}",
            })
            score += scoring.SCORING["investment_firm_pts"]
            break

    # ------------------------------------------------------------------
    # 4. Bet concentration + size signals
    # ------------------------------------------------------------------
    yes_only = [s for s, m in user_positions.items() if m.get("yes") and not m.get("no")]
    both_sides = [s for s, m in user_positions.items() if m.get("yes") and m.get("no")]
    total_markets = len(user_positions)

    # Aggregate USD values when the positions file has them (requires a fresh
    # holder fetch — older files only store yes/no booleans).
    total_yes_usd = sum(m.get("yes_value_usd") or 0.0 for m in user_positions.values())
    total_no_usd  = sum(m.get("no_value_usd")  or 0.0 for m in user_positions.values())
    total_bet_usd = total_yes_usd + total_no_usd
    max_single_usd = max(
        (max(m.get("yes_value_usd") or 0.0, m.get("no_value_usd") or 0.0)
         for m in user_positions.values()),
        default=0.0,
    )
    has_bet_data = total_bet_usd > 0

    # Concentration flag (include USD when available)
    if total_markets == 1 and yes_only:
        f: dict = {"type": "single_market_high_conviction", "market": yes_only[0], "points": 3}
        if has_bet_data:
            f["yes_value_usd"] = round(total_yes_usd, 2)
        flags.append(f)
        score += 3
    elif total_markets <= 3 and yes_only and len(yes_only) == total_markets:
        f = {"type": "few_markets_all_yes", "markets": yes_only, "points": 2}
        if has_bet_data:
            f["total_yes_usd"] = round(total_yes_usd, 2)
        flags.append(f)
        score += 2

    if both_sides:
        flags.append({"type": "hedging_both_sides", "count": len(both_sides), "points": -2})
        score -= 2

    # Bet size bonus (independent of concentration — big ≠ single-market)
    if has_bet_data and total_bet_usd >= 50:
        if total_bet_usd >= 5000:
            bet_pts = 4
        elif total_bet_usd >= 1000:
            bet_pts = 3
        elif total_bet_usd >= 200:
            bet_pts = 2
        else:
            bet_pts = 1
        flags.append({
            "type": "large_bet",
            "total_yes_usd": round(total_yes_usd, 2),
            "total_no_usd":  round(total_no_usd, 2),
            "max_single_usd": round(max_single_usd, 2),
            "points": bet_pts,
        })
        score += bet_pts

    # ------------------------------------------------------------------
    # 5. Location signal (minor)
    # ------------------------------------------------------------------
    for loc in all_locations:
        for hub in FINANCIAL_HUB_CITIES:
            if hub in loc:
                flags.append({"type": "financial_hub_location", "location": loc, "points": 1})
                score += 1
                break

    for cc in all_country_codes:
        if cc in FINANCIAL_HUB_COUNTRIES:
            flags.append({"type": "financial_hub_country", "country_code": cc, "points": 1})
            score += 1
            break

    # ------------------------------------------------------------------
    # 6. Falcon on-chain analytics
    # ------------------------------------------------------------------
    falcon_f, falcon_s = scoring.falcon_flags(profile_data)
    flags.extend(falcon_f)
    score += falcon_s

    return {
        "username": username,
        "score": score,
        "flags": flags,
        "markets_held": total_markets,
        "yes_positions": yes_only,
        "profiles_found": [p["site"] for p in profile_data.get("profiles", [])],
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading market positions...", file=sys.stderr)
    positions = json.load(open(POSITIONS_FILE))

    print("Scoring users...", file=sys.stderr)
    profile_files = glob.glob(f"{RESULTS_DIR}/*.json")
    results = []

    for fpath in profile_files:
        data = json.load(open(fpath))
        if "username" not in data:
            continue
        username = data["username"]
        result = score_user(username, data, positions)
        if result["score"] > 0:
            results.append(result)

    results.sort(key=lambda x: -x["score"])

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json.dump(results, open(OUTPUT_FILE, "w"), indent=2)
    print(f"Wrote {len(results)} scored users to {OUTPUT_FILE}", file=sys.stderr)

    # Console: hide users whose only flag is a bare bet-concentration signal —
    # those are too weak to investigate. Require at least one substantive flag.
    # large_bet on its own (no professional signal) is also excluded.
    _CONCENTRATION_ONLY = {
        "single_market_high_conviction", "few_markets_all_yes",
        "financial_hub_location", "financial_hub_country",
        "hedging_both_sides", "large_bet",
        # Falcon signals on their own are weak — require at least one OSINT or
        # company-affiliation flag alongside them before surfacing in the console.
        "falcon_large_pnl", "falcon_high_roi", "falcon_high_win_rate",
        "falcon_high_sharpe", "falcon_concentrated_bets",
    }
    display = [
        r for r in results
        if any(f["type"] not in _CONCENTRATION_ONLY for f in r["flags"])
    ]

    print(f"\n{'='*76}")
    print(f"INSIDER TRADING RISK REPORT  —  top {min(30, len(display))} of {len(display)} substantive hits  ({len(results)} total flagged)")
    print(f"{'='*76}")

    def _fmt_usd(v: float) -> str:
        return f"${v:,.0f}" if v >= 1 else f"${v:.2f}"

    for r in display[:30]:
        print(f"\n  {r['username']:32s}  score={r['score']:3d}  markets={r['markets_held']}")
        for flag in r["flags"]:
            ftype = flag["type"]
            pts = flag.get("points", 0)
            ctx = flag.get("context", "")
            if ftype == "direct_company_affiliation_linkedin":
                print(f"    [{pts:+d}] LINKEDIN: '{flag['keyword']}' → {flag['position']} on {flag['market']}")
                print(f"           context: {ctx}")
            elif ftype == "direct_company_affiliation":
                print(f"    [{pts:+d}] DIRECT:   '{flag['keyword']}' → {flag['position']} on {flag['market']}")
                print(f"           context: {ctx}")
            elif ftype == "corporate_email_domain":
                print(f"    [{pts:+d}] EMAIL:    {flag['email']}  →  {flag['position']} on {flag['market']}")
            elif ftype == "company_affiliation_no_position":
                print(f"    [+{pts}] AFFIL:    '{flag['keyword']}' in profile (no position held)")
                print(f"           context: {ctx}")
            elif ftype == "investment_bank":
                print(f"    [{pts:+d}] BANK:     {flag['matched']}")
                print(f"           context: {ctx}")
            elif ftype == "vc_firm":
                print(f"    [{pts:+d}] VC:       {flag['matched']}")
                print(f"           context: {ctx}")
            elif ftype == "securities_law_firm":
                print(f"    [{pts:+d}] LAW:      {flag['matched']}")
                print(f"           context: {ctx}")
            elif ftype == "big4_accounting":
                print(f"    [{pts:+d}] BIG4:     {flag['matched']}")
                print(f"           context: {ctx}")
            elif ftype == "big_tech_employee":
                print(f"    [{pts:+d}] BIGTECH:  {flag['matched']}")
                print(f"           context: {ctx}")
            elif ftype == "investment_firm_company":
                print(f"    [{pts:+d}] INV_FIRM: {flag['company']}")
                print(f"           context: {ctx}")
            elif ftype == "single_market_high_conviction":
                usd = f"  [{_fmt_usd(flag['yes_value_usd'])} YES]" if "yes_value_usd" in flag else ""
                print(f"    [{pts:+d}] FOCUS:    single-market YES bet → {flag['market']}{usd}")
            elif ftype == "few_markets_all_yes":
                usd = f"  [{_fmt_usd(flag['total_yes_usd'])} YES total]" if "total_yes_usd" in flag else ""
                print(f"    [{pts:+d}] FOCUS:    {len(flag['markets'])} markets, all YES{usd}")
            elif ftype == "large_bet":
                parts = []
                if flag["total_yes_usd"] > 0:
                    parts.append(f"{_fmt_usd(flag['total_yes_usd'])} YES")
                if flag["total_no_usd"] > 0:
                    parts.append(f"{_fmt_usd(flag['total_no_usd'])} NO")
                print(f"    [{pts:+d}] BET:      {' + '.join(parts)}  (max single: {_fmt_usd(flag['max_single_usd'])})")
            elif ftype == "hedging_both_sides":
                print(f"    [{pts:+d}] HEDGE:    holds both YES+NO on {flag['count']} market(s)")
            elif ftype == "financial_hub_location":
                print(f"    [{pts:+d}] LOC:      {flag['location']}")
            elif ftype == "falcon_large_pnl":
                print(f"    [{pts:+d}] FALCON:   ${flag['total_pnl']:,} lifetime PnL")
            elif ftype == "falcon_high_roi":
                print(f"    [{pts:+d}] FALCON:   {flag['roi_pct']}% ROI over {flag['total_trades']} trades")
            elif ftype == "falcon_high_win_rate":
                print(f"    [{pts:+d}] FALCON:   {float(flag['win_rate']):.1%} win rate")
            elif ftype == "falcon_high_sharpe":
                print(f"    [{pts:+d}] FALCON:   Sharpe ratio {flag['sharpe_ratio']}")
            elif ftype == "falcon_concentrated_bets":
                print(f"    [{pts:+d}] FALCON:   category diversity {flag['diversity_score']} (concentrated)")

    print(f"\n{'='*76}")
    print(f"Full results → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
