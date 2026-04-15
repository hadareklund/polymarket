"""
run_all.py — Run scrape_pending site scrapers and emit clean JSON output.

Usage:
    python3 run_all.py <username> [--sites site1,site2,...] [--out report.json]
    python3 run_all.py --usernames-file users.txt [--sites ...] [--out-dir reports]

Sites are auto-discovered from *_user_info.py files in this folder.
Current defaults:
    angellist, bitcointalk, crunchbase, discord, doxbin,
    linkedin, pastebin, quora, researchgate, tradingview

Environment variables for auth-gated sites:
  LINKEDIN_LI_AT        — li_at cookie from logged-in LinkedIn session
  DISCORD_BOT_TOKEN     — Discord bot token (Bot xxxx)
  CRUNCHBASE_API_KEY    — Crunchbase v4 API key
  PASTEBIN_API_KEY      — Pastebin dev key  (optional, enhances pastebin)
  PASTEBIN_PASSWORD     — Pastebin password (optional, for own account)
  QUORA_M_B             — m-b cookie from logged-in Quora session
  RG_COOKIE             — Full cookie string from ResearchGate session

Sites that strictly require a secret key / token (cannot work without one):
  • discord     → DISCORD_BOT_TOKEN  (no public user endpoint at all)
  • crunchbase  → CRUNCHBASE_API_KEY (API always requires user_key param)

Sites that work without auth but return more with one:
    • linkedin    → LINKEDIN_LI_AT (without cookie often limited/blocked)
  • pastebin    → PASTEBIN_API_KEY + PASTEBIN_PASSWORD (own private pastes)
  • quora       → QUORA_M_B (Cloudflare bypass)
  • researchgate→ RG_COOKIE (Cloudflare bypass)

Sites that work fully without any auth:
  • angellist / wellfound
  • bitcointalk
    • doxbin (domain/challenge dependent)
  • tradingview  (HTML)
"""

import sys, os, json, argparse, importlib, traceback, re
from datetime import datetime, timezone

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _discover_sites() -> list[str]:
    sites = []
    for name in os.listdir(SCRIPT_DIR):
        if not name.endswith("_user_info.py"):
            continue
        if name.startswith("_"):
            continue
        sites.append(name[: -len("_user_info.py")])
    return sorted(sites)


ALL_SITES = _discover_sites()

# Sites that STRICTLY require a secret key — skip with a clear notice
REQUIRES_KEY = {
    "discord": "DISCORD_BOT_TOKEN",
    "crunchbase": "CRUNCHBASE_API_KEY",
}

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")


def _looks_like_html(text: str) -> bool:
    low = text.lower()
    if "<!doctype html" in low or "<html" in low or "<body" in low:
        return True
    tag_hits = len(re.findall(r"<[^>]+>", text))
    return tag_hits >= 8


def _clean_text_value(text: str, max_len: int = 1200) -> str:
    cleaned = text
    if _looks_like_html(cleaned):
        cleaned = HTML_TAG_RE.sub(" ", cleaned)
    cleaned = WHITESPACE_RE.sub(" ", cleaned).strip()
    if len(cleaned) > max_len:
        return cleaned[:max_len] + " ...[truncated]"
    return cleaned


def _sanitize_value(value, include_tracebacks: bool):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "traceback" and not include_tracebacks:
                continue
            out[k] = _sanitize_value(v, include_tracebacks)
        return out

    if isinstance(value, list):
        compact = [_sanitize_value(v, include_tracebacks) for v in value[:80]]
        if len(value) > 80:
            compact.append({"_note": f"list truncated at 80 of {len(value)} items"})
        return compact

    if isinstance(value, str):
        return _clean_text_value(value, max_len=500)

    return value


def _safe_filename(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("_") or "user"


def run_scraper(site: str, username: str) -> dict:
    module_name = f"{site}_user_info"
    try:
        if SCRIPT_DIR not in sys.path:
            sys.path.insert(0, SCRIPT_DIR)
        mod = importlib.import_module(module_name)
        return mod.scrape(username)
    except ModuleNotFoundError as e:
        # If the missing name is the scraper module itself, module is absent.
        # Otherwise a dependency inside that module is missing.
        if e.name == module_name:
            return {
                "site": site,
                "status": "error",
                "reason": "scraper module not found",
            }
        return {
            "site": site,
            "status": "error",
            "reason": f"missing dependency: {e.name}",
        }
    except Exception as e:
        return {
            "site": site,
            "status": "error",
            "reason": str(e),
            "traceback": traceback.format_exc(),
        }


def run_for_username(
    username: str,
    sites: list[str],
    discord_id: str | None,
    crunchbase_slug: str | None,
    include_tracebacks: bool,
) -> dict:
    results = {
        "query_username": username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": {},
        "skipped": {},
    }

    for site in sites:
        if site == "discord":
            if not os.environ.get("DISCORD_BOT_TOKEN"):
                results["skipped"][site] = "DISCORD_BOT_TOKEN not set"
                continue
            lookup = discord_id or username
        elif site == "crunchbase":
            if not os.environ.get("CRUNCHBASE_API_KEY"):
                results["skipped"][site] = "CRUNCHBASE_API_KEY not set"
                continue
            lookup = crunchbase_slug or username
        else:
            lookup = username

        print(f"  → scraping {site} for '{lookup}'...", file=sys.stderr)
        result = run_scraper(site, lookup)
        results["results"][site] = _sanitize_value(result, include_tracebacks)

    return results


def main():
    parser = argparse.ArgumentParser(description="Multi-site user info scraper")
    parser.add_argument("username", nargs="*", help="Username(s) to look up")
    parser.add_argument(
        "--usernames-file",
        help="Path to text file with one username per line (comments with # allowed)",
    )
    parser.add_argument(
        "--sites",
        help="Comma-separated list of sites to query (default: all)",
        default=",".join(ALL_SITES),
    )
    parser.add_argument("--out", help="Output JSON file (single-user mode)")
    parser.add_argument(
        "--out-dir",
        help="Directory for per-user JSON files (used automatically for multi-user mode)",
    )
    parser.add_argument(
        "--discord-id",
        help="Discord numeric user ID (required for discord)",
        default=None,
    )
    parser.add_argument(
        "--crunchbase-slug",
        help="Crunchbase person slug (default: username)",
        default=None,
    )
    parser.add_argument(
        "--include-tracebacks",
        action="store_true",
        help="Include exception tracebacks in output JSON",
    )
    args = parser.parse_args()

    sites = [s.strip() for s in args.sites.split(",") if s.strip()]
    unknown_sites = [s for s in sites if s not in ALL_SITES]
    if unknown_sites:
        print(
            f"Error: unsupported sites requested: {', '.join(unknown_sites)}",
            file=sys.stderr,
        )
        print(f"Supported sites: {', '.join(ALL_SITES)}", file=sys.stderr)
        sys.exit(2)

    usernames: list[str] = list(args.username or [])
    if args.usernames_file:
        try:
            with open(args.usernames_file, "r", encoding="utf-8") as f:
                for line in f:
                    candidate = line.strip()
                    if candidate and not candidate.startswith("#"):
                        usernames.append(candidate)
        except Exception as e:
            print(f"Error: could not read usernames file: {e}", file=sys.stderr)
            sys.exit(2)

    # de-duplicate while preserving order
    seen = set()
    deduped: list[str] = []
    for u in usernames:
        if u not in seen:
            deduped.append(u)
            seen.add(u)
    usernames = deduped

    if not usernames:
        print(
            "Error: provide at least one username or --usernames-file", file=sys.stderr
        )
        sys.exit(2)

    if len(usernames) == 1:
        username = usernames[0]
        results = run_for_username(
            username,
            sites,
            args.discord_id,
            args.crunchbase_slug,
            args.include_tracebacks,
        )
        output = json.dumps(results, indent=2, ensure_ascii=False)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(output)
            print(f"\n✓ Saved to {args.out}", file=sys.stderr)
        else:
            print(output)
        return

    out_dir = args.out_dir or "reports"
    os.makedirs(out_dir, exist_ok=True)
    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "sites": sites,
        "count": len(usernames),
        "users": {},
    }

    print(
        f"Running {len(sites)} site scrapers for {len(usernames)} users...",
        file=sys.stderr,
    )
    for username in usernames:
        print(f"\n• user: {username}", file=sys.stderr)
        report = run_for_username(
            username,
            sites,
            args.discord_id,
            args.crunchbase_slug,
            args.include_tracebacks,
        )
        filename = _safe_filename(username) + ".json"
        path = os.path.join(out_dir, filename)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        summary["users"][username] = {
            "file": path,
            "scraped_sites": sorted(report["results"].keys()),
            "skipped_sites": report["skipped"],
        }
        print(f"  ✓ saved {path}", file=sys.stderr)

    summary_path = os.path.join(out_dir, "_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\n✓ Summary saved to {summary_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
