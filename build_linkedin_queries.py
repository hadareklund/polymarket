#!/usr/bin/env python3
"""
Build a LinkedIn scraper input file from existing Polymarket user profiles.

For each user, picks the best available real name (GitHub > chess.com > HuggingFace),
then extracts company and location from GitHub. Filters out names that look like
handles, org names, or garbage.

Output: results/<slug>_analysis/linkedin_queries.json
  [
    {
      "polymarket_username": "loganj",
      "name": "Logan Johnson",
      "company": "Square, Inc.",
      "location": "New York, NY",
      "name_source": "GitHub"
    },
    ...
  ]
"""

import json
import glob
import re
import os
import sys

# Slug can be overridden via first CLI arg: python3 build_linkedin_queries.py <slug>
_SLUG = sys.argv[1] if len(sys.argv) > 1 else "ipos-before-2027"

RESULTS_DIR = f"results/{_SLUG}_full_holder_usernames"
OUTPUT_DIR  = f"results/{_SLUG}_analysis"
OUTPUT_FILE = f"{OUTPUT_DIR}/linkedin_queries.json"

NAME_PRIORITY = [
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

REJECT_WORDS = {
    "inc", "llc", "ltd", "corp", "university", "institute",
    "school", "college", "studio", "labs", "lab", "team",
    "official", "account", "user", "null", "none", "test",
    "admin", "root", "anonymous", "unknown", "n/a",
}


def looks_like_real_name(s: str) -> bool:
    if not s:
        return False
    # Normalize whitespace (chess.com has newline-padded names)
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
        # All-caps token longer than 4 chars = acronym or org abbreviation
        if len(p) > 4 and p.isupper():
            return False
    low = s.lower()
    if any(w in low.split() for w in REJECT_WORDS):
        return False
    # Reject non-latin scripts (CJK, Arabic, Devanagari) — not searchable on LinkedIn
    if _CJK_RE.search(s):
        return False
    return True


def clean_name(s: str) -> str:
    return " ".join(s.split())


def extract_query(data: dict) -> dict | None:
    profiles_by_site = {p["site"]: p for p in data.get("profiles", [])}

    # Pick best name
    chosen_name = None
    name_source = None

    # Codeforces stores first/last separately
    cf = profiles_by_site.get("Codeforces")
    if cf:
        first = (cf.get("first_name") or "").strip()
        last  = (cf.get("last_name") or "").strip()
        combined = f"{first} {last}".strip()
        if looks_like_real_name(combined):
            chosen_name = clean_name(combined)
            name_source = "Codeforces"

    if not chosen_name:
        for site, field in NAME_PRIORITY:
            p = profiles_by_site.get(site)
            if p:
                raw = (p.get(field) or "").strip()
                if looks_like_real_name(raw):
                    chosen_name = clean_name(raw)
                    name_source = site
                    break

    if not chosen_name:
        return None

    # Company from GitHub (most reliable professional context)
    # If the field lists multiple orgs (e.g. "@microsoft @dotnet"), take only the first.
    company = ""
    gh = profiles_by_site.get("GitHub")
    if gh:
        raw_company = (gh.get("company") or "").strip()
        # Split on whitespace and take first non-empty token, stripping leading @
        tokens = raw_company.split()
        first = tokens[0].lstrip("@").rstrip(",.;") if tokens else ""
        if first and first.lower() not in ("none", "null", "n/a", "private", "at large"):
            company = first

    # Location: prefer GitHub, fall back to chess.com
    location = ""
    for site in ("GitHub", "chess.com", "Duolingo"):
        p = profiles_by_site.get(site)
        if p:
            loc = (p.get("location") or "").strip()
            if loc and len(loc) <= 100:
                location = loc
                break

    # Confidence: high if name has a full last name (>1 char), otherwise low
    parts = chosen_name.split()
    name_confidence = "high" if len(parts) >= 2 and len(parts[-1]) > 1 else "low"

    return {
        "polymarket_username": data["username"],
        "name": chosen_name,
        "name_source": name_source,
        "name_confidence": name_confidence,
        "company": company,
        "location": location,
    }


def main():
    files = glob.glob(f"{RESULTS_DIR}/*.json")
    queries = []
    skipped = 0

    for fpath in sorted(files):
        data = json.load(open(fpath))
        if "username" not in data:
            continue
        q = extract_query(data)
        if q:
            queries.append(q)
        else:
            skipped += 1

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    json.dump(queries, open(OUTPUT_FILE, "w"), indent=2)

    with_company = sum(1 for q in queries if q["company"])
    with_location = sum(1 for q in queries if q["location"])
    by_source = {}
    for q in queries:
        by_source[q["name_source"]] = by_source.get(q["name_source"], 0) + 1

    print(f"LinkedIn queries written:  {len(queries)}")
    print(f"Skipped (no usable name):  {skipped}")
    print(f"With company field:        {with_company}")
    print(f"With location field:       {with_location}")
    print(f"\nName sources:")
    for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {cnt:4d}  {src}")
    print(f"\nOutput → {OUTPUT_FILE}")

    print(f"\nSample (first 10):")
    for q in queries[:10]:
        print(f"  {q['polymarket_username']:25s} | {q['name']:25s} | {q['company']:20s} | {q['location']}")


if __name__ == "__main__":
    main()
