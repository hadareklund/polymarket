#!/usr/bin/env python3
"""
auto_monitor.py — Run the polywhaler pipeline, analyse results with Claude Code,
                  post the analysis to a Telegram channel.

Uses `claude -p` (Claude Code CLI) for analysis — no separate API key needed,
runs against your existing Claude subscription.

Required env / .env keys:
    TELEGRAM_BOT_TOKEN  — Telegram bot token (from @BotFather)
    TELEGRAM_CHAT_ID    — Channel or chat ID to post to (e.g. -1001234567890)

Optional:
    TELEGRAM_TOPIC_ID   — Message-thread ID if posting to a forum-channel topic

Usage:
    python3 auto_monitor.py
    python3 auto_monitor.py --threshold 20 --pages 4
    python3 auto_monitor.py --no-osint          # skip OSINT, analyse cached data
    python3 auto_monitor.py --no-telegram       # run + analyse, skip posting
    python3 auto_monitor.py --dry-run           # use today's cached data, skip monitor
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import subprocess
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Env / config
# ---------------------------------------------------------------------------

def _load_env() -> None:
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())


def _require(key: str) -> str:
    val = os.environ.get(key, "")
    if not val:
        print(f"Error: {key} not set. Add it to .env or export it.", file=sys.stderr)
        sys.exit(1)
    return val


# ---------------------------------------------------------------------------
# Step 1: run polywhaler_monitor.py
# ---------------------------------------------------------------------------

def run_monitor(args: argparse.Namespace) -> Path:
    cmd = [
        sys.executable, str(SCRIPT_DIR / "polywhaler_monitor.py"),
        "--threshold",       str(args.threshold),
        "--pages",           str(args.pages),
        "--workers",         str(args.workers),
        "--user-workers",    str(args.user_workers),
        "--timeout",         str(args.timeout),
        "--linkedin-engine", args.linkedin_engine,
    ]
    if args.no_osint:
        cmd.append("--no-osint")
    if args.no_linkedin:
        cmd.append("--no-linkedin")

    print("=" * 72)
    print("STEP 1 — Running polywhaler monitor…")
    print("=" * 72)
    proc = subprocess.run(cmd, text=True)
    if proc.returncode > 1:
        print(f"Error: polywhaler_monitor.py crashed (exit {proc.returncode}) — aborting run",
              file=sys.stderr)
        sys.exit(proc.returncode)
    elif proc.returncode == 1:
        print(f"Warning: polywhaler_monitor.py exited 1 (partial run, data checkpointed)",
              file=sys.stderr)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return SCRIPT_DIR / "results" / "polywhaler" / date_str


# ---------------------------------------------------------------------------
# Step 2: build prompt from analysis.json
# ---------------------------------------------------------------------------

_SYSTEM = (
    "You are an OSINT analyst specialising in prediction-market insider trading. "
    "You receive a structured JSON report of traders flagged on Polymarket.\n\n"
    "Each trader entry may include:\n"
    "- identity: real_name, employer (from LinkedIn title), linkedin_url, linkedin_snippet, "
    "github_company, name_source\n"
    "- flags: OSINT signals (entity match, employer, finance keywords)\n"
    "- on_chain: Falcon API metrics — lifetime_pnl (total profit $), lifetime_roi_pct (%), "
    "lifetime_trades (count), win_rate (0-1), sharpe_ratio, category_diversity (0=concentrated, 1=broad)\n\n"
    "Rules:\n"
    "- Only include traders who are LIKELY insiders: large position + credible real-world profile "
    "(LinkedIn, employer, verified identity) OR exceptional on-chain metrics suggesting information advantage "
    "(win_rate > 0.75 + concentrated category bets + large trade). "
    "A high polywhaler score alone is NOT enough — require at least one corroborating signal.\n"
    "- For each included trader write 2-4 lines:\n"
    "  • *username* (Real Name if known) — market title, $size, outcome\n"
    "  • Why they look like an insider — cite the specific OSINT flag or on-chain metric. "
    "If employer is present, state it explicitly (e.g. 'Works at Goldman Sachs per LinkedIn'). "
    "If linkedin_snippet has useful detail (role, industry), quote the relevant part.\n"
    "  • LinkedIn URL if available.\n"
    "- End with a single *Recommended action:* line.\n"
    "- If nobody clears the bar, reply with only: 'No high-confidence insiders today.'\n\n"
    "Format: Telegram plain text, bold via *word*, no tables. Keep total under 3000 characters."
)


def _trader_summary(r: dict) -> dict:
    summary: dict = {
        "username":       r["username"],
        "our_score":      r["our_score"],
        "pw_score":       r["polywhaler_insider_score"],
        "market":         r["market_title"],
        "category":       r["market_category"],
        "outcome":        r["outcome"],
        "trade_usd":      round(r["trade_size"]),
        "profiles_found": r["profiles_found"],
        "flags": [
            {k: v for k, v in f.items() if k != "points"}
            for f in r["flags"]
        ],
        "extra_markets": [
            {"market": t["title"], "outcome": t["outcome"], "usd": round(t["size"])}
            for t in r.get("all_trades", [])[1:4]
        ],
    }
    if r.get("identity"):
        summary["identity"] = r["identity"]
    analytics = r.get("polymarket_analytics", {})
    perf = analytics.get("lifetime_performance", {})
    w360 = analytics.get("wallet_360_30d", {})
    if perf or w360:
        summary["on_chain"] = {
            k: v for k, v in {
                "lifetime_pnl":    perf.get("total_pnl"),
                "lifetime_roi_pct": perf.get("roi_pct"),
                "lifetime_trades": perf.get("total_trades"),
                "win_rate":        w360.get("win_rate"),
                "sharpe_ratio":    w360.get("sharpe_ratio"),
                "category_diversity": w360.get("category_diversity_score"),
                "window_days":     w360.get("window_days"),
            }.items() if v is not None
        }
    return summary


def _portfolio_stats_block() -> str:
    """Return a short portfolio performance summary to include in the Claude prompt."""
    portfolio_file = SCRIPT_DIR / "results" / "watchlist_portfolio.json"
    if not portfolio_file.exists():
        return ""
    try:
        positions = json.loads(portfolio_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return ""

    decided = [p for p in positions if p.get("status") in ("won", "lost")]
    if not decided:
        return ""

    won     = sum(1 for p in decided if p["status"] == "won")
    priced  = [p for p in decided if (p.get("entry_price") or 0) > 0]
    total_pnl   = sum(p.get("pnl_usd", 0) for p in priced)
    total_staked = sum(p.get("paper_stake", 100) for p in priced)
    win_rate = f"{won / len(decided):.0%}"
    pnl_str  = (
        f"${total_pnl:+,.0f} ({total_pnl / total_staked * 100:+.1f}%)"
        if total_staked > 0 else f"${total_pnl:+,.0f}"
    )

    # Recent 30-day stats
    cutoff30 = (datetime.now(timezone.utc) - __import__("datetime").timedelta(days=30)).strftime("%Y-%m-%d")
    recent30 = [p for p in decided if p.get("date_flagged", "") >= cutoff30]
    r30_won  = sum(1 for p in recent30 if p["status"] == "won")
    r30_wr   = f"{r30_won / len(recent30):.0%}" if recent30 else "n/a"

    return (
        f"Portfolio performance (paper $100/trade): "
        f"all-time win rate {win_rate} ({won}/{len(decided)} decided), "
        f"P&L {pnl_str}; "
        f"last 30 days win rate {r30_wr} ({r30_won}/{len(recent30)} decided).\n\n"
    )


def build_prompt(out_dir: Path) -> str | None:
    analysis_file = out_dir / "analysis.json"
    if not analysis_file.exists():
        print(f"No analysis.json in {out_dir} — nothing to analyse.", file=sys.stderr)
        return None

    results: list[dict] = json.loads(analysis_file.read_text(encoding="utf-8"))
    if not results:
        return None

    # Deduplicate by username — keep the highest-scored entry per trader
    seen: dict[str, dict] = {}
    for r in results:
        u = r["username"]
        if u not in seen or r["our_score"] > seen[u]["our_score"]:
            seen[u] = r
    traders = [_trader_summary(r) for r in seen.values()]

    prompt = (
        f"Date: {out_dir.name}\n"
        f"Traders flagged: {len(traders)}\n\n"
        f"Data:\n```json\n{json.dumps(traders, indent=2, ensure_ascii=False)}\n```\n\n"
    )

    updates_file = out_dir / "watchlist_updates.json"
    if updates_file.exists():
        try:
            updates: list[dict] = json.loads(updates_file.read_text(encoding="utf-8"))
            if updates:
                prompt += (
                    f"Previously-flagged traders whose markets just resolved "
                    f"({len(updates)} outcome(s)):\n"
                    f"```json\n{json.dumps(updates, indent=2, ensure_ascii=False)}\n```\n\n"
                )
        except (json.JSONDecodeError, OSError):
            pass

    stats_block = _portfolio_stats_block()
    if stats_block:
        prompt += stats_block

    prompt += "Write the intelligence brief now."
    return prompt


# ---------------------------------------------------------------------------
# Step 3: call Claude via `claude -p`
# ---------------------------------------------------------------------------

def call_claude(prompt: str, model: str) -> str:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        print("Error: `claude` CLI not found in PATH.", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 72)
    print("STEP 2 — Sending to Claude for analysis…")
    print("=" * 72)

    full_prompt = f"{_SYSTEM}\n\n---\n\n{prompt}"

    proc = subprocess.run(
        [claude_bin, "-p", "--model", model, full_prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if proc.returncode != 0:
        err = proc.stderr.strip()
        print(f"Error: claude exited {proc.returncode}: {err}", file=sys.stderr)
        sys.exit(1)

    return proc.stdout.strip()


# ---------------------------------------------------------------------------
# Step 4: post to Telegram
# ---------------------------------------------------------------------------

_TG_BASE  = "https://api.telegram.org/bot{token}/{method}"
_MAX_CHUNK = 4000


def _tg(token: str, method: str, payload: dict) -> dict:
    url  = _TG_BASE.format(token=token, method=method)
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _tg_with_retry(token: str, method: str, payload: dict) -> dict:
    """Call Telegram API with exponential backoff for transient non-400 errors."""
    delays = (2, 4, 8)
    for attempt in range(len(delays) + 1):
        try:
            return _tg(token, method, payload)
        except urllib.error.HTTPError as exc:
            if exc.code == 400 or attempt == len(delays):
                raise
            time.sleep(delays[attempt])
    raise RuntimeError("unreachable")


def _health_summary(out_dir: Path) -> str:
    """One-line run health summary built from output files."""
    trades_n = scored_n = 0
    trades_file = out_dir / "trades.json"
    if trades_file.exists():
        try:
            trades_n = len(json.loads(trades_file.read_text()))
        except Exception:
            pass
    analysis_file = out_dir / "analysis.json"
    if analysis_file.exists():
        try:
            scored_n = len(json.loads(analysis_file.read_text()))
        except Exception:
            pass
    extra = ""
    stats_file = out_dir / "run_stats.json"
    if stats_file.exists():
        try:
            s = json.loads(stats_file.read_text())
            new_n = s.get("new_traders", "?")
            bl = (s.get("blocklisted_skipped_osint") or 0) + (s.get("blocklisted_skipped_score") or 0)
            extra = f"  new={new_n}"
            if bl:
                extra += f"  blocklisted={bl}"
        except Exception:
            pass
    return f"Health: trades={trades_n}  scored={scored_n}{extra}"


def _split(text: str, limit: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    length = 0
    for line in text.splitlines(keepends=True):
        if length + len(line) > limit and current:
            chunks.append("".join(current))
            current = []
            length = 0
        current.append(line)
        length += len(line)
    if current:
        chunks.append("".join(current))
    return chunks or [text[:limit]]


def post_telegram(text: str, token: str, chat_id: str, topic_id: str | None) -> None:
    chunks = _split(text, _MAX_CHUNK)
    print(f"\n{'='*72}")
    print(f"STEP 3 — Posting {len(chunks)} message(s) to Telegram…")
    print("=" * 72)

    for i, chunk in enumerate(chunks, 1):
        payload: dict = {
            "chat_id":    chat_id,
            "text":       chunk,
            "parse_mode": "Markdown",
        }
        if topic_id:
            payload["message_thread_id"] = int(topic_id)
        try:
            resp = _tg_with_retry(token, "sendMessage", payload)
            if resp.get("ok"):
                print(f"  [{i}/{len(chunks)}] sent (msg_id={resp['result']['message_id']})")
            else:
                print(f"  [{i}/{len(chunks)}] failed: {resp}", file=sys.stderr)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode()
            # Retry as plain text if Telegram rejects our Markdown
            if exc.code == 400 and ("parse_mode" in body or "can't parse" in body.lower()):
                payload.pop("parse_mode")
                resp = _tg_with_retry(token, "sendMessage", payload)
                if resp.get("ok"):
                    print(f"  [{i}/{len(chunks)}] sent (plain-text fallback)")
                else:
                    print(f"  [{i}/{len(chunks)}] still failed: {resp}", file=sys.stderr)
            else:
                raise
        if i < len(chunks):
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# Step 5: pipeline self-review via Claude
# ---------------------------------------------------------------------------

_REVIEW_SYSTEM = """\
You are performing a meta-analysis of a Polymarket insider-trading intelligence pipeline.
Your job is to evaluate how well today's run performed and propose concrete improvements.

You have been given:
1. The intelligence brief that was sent to the operator via Telegram (the pipeline's output)
2. The full scored-trader data from analysis.json (the raw evidence)
3. The project's CLAUDE.md (already loaded as context), which describes the full pipeline
   architecture, scoring weights, data sources, and goals

Evaluate the following dimensions:

**Signal quality** — Are the flagged traders genuinely suspicious? Which flags are the most
and least predictive of real insider activity?  Point out any obvious false positives.

**Coverage gaps** — What data is absent that would materially strengthen or weaken the cases?
(e.g. missing Falcon enrichment, no LinkedIn hit, no OSINT profile at all)

**Scoring calibration** — Are the point weights in score_against_market() well-balanced?
Are any flags over- or under-weighted relative to their actual information value?

**Pipeline reliability** — Signs of collection failures: empty profiles, skipped enrichment,
dedup issues, traders with polywhaler_insider_score but zero OSINT.

**Output quality** — Is the Telegram brief clear, actionable, and appropriately concise?
Does it surface the right traders? Does it miss anyone from the raw data who should be included?

After your evaluation, propose 3–5 specific, actionable improvements ranked by expected impact.
For each: state what to change, why it would help, and which file/component to modify.

Be direct and critical. If today's run produced low-quality results, say so clearly.\
"""


def call_pipeline_review(brief: str, out_dir: Path, model: str) -> str | None:
    """Run a Claude meta-analysis of today's pipeline output, return the review text."""
    claude_bin = shutil.which("claude")
    if not claude_bin:
        return None

    print("\n" + "=" * 72)
    print("STEP 5 — Running pipeline self-review with Claude…")
    print("=" * 72)

    analysis_json = ""
    analysis_file = out_dir / "analysis.json"
    if analysis_file.exists():
        try:
            data = json.loads(analysis_file.read_text(encoding="utf-8"))
            analysis_json = json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            pass

    stats_block = ""
    stats_file = out_dir / "run_stats.json"
    if stats_file.exists():
        try:
            stats_block = (
                "\n=== RUN STATS ===\n```json\n"
                + stats_file.read_text(encoding="utf-8")
                + "\n```\n"
            )
        except Exception:
            pass

    prompt = (
        f"Date: {out_dir.name}\n\n"
        f"=== TELEGRAM BRIEF SENT TO OPERATOR ===\n{brief}\n\n"
        f"=== FULL SCORED TRADER DATA (analysis.json) ===\n"
        f"```json\n{analysis_json}\n```\n"
        f"{stats_block}"
        f"\nNow write your pipeline evaluation and improvement suggestions."
    )

    full_prompt = f"{_REVIEW_SYSTEM}\n\n---\n\n{prompt}"

    try:
        proc = subprocess.run(
            [claude_bin, "-p", "--model", model, full_prompt],
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(SCRIPT_DIR),
        )
        if proc.returncode != 0:
            err = proc.stderr.strip()[:300]
            print(f"  Warning: pipeline review exited {proc.returncode}: {err}", file=sys.stderr)
            return None
        return proc.stdout.strip()
    except subprocess.TimeoutExpired:
        print("  Warning: pipeline review timed out after 180 s", file=sys.stderr)
        return None
    except Exception as exc:
        print(f"  Warning: pipeline review error: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Polywhaler → Claude Code CLI → Telegram pipeline."
    )
    p.add_argument("--threshold",       type=int,  default=20)
    p.add_argument("--pages",           type=int,  default=4)
    p.add_argument("--workers",         type=int,  default=5)
    p.add_argument("--user-workers",    type=int,  default=8)
    p.add_argument("--timeout",         type=int,  default=20)
    p.add_argument("--no-osint",        action="store_true")
    p.add_argument("--no-linkedin",     action="store_true")
    p.add_argument("--linkedin-engine", default="brave",
                   choices=["brave", "bing", "ddg", "google"])
    p.add_argument("--model",           default="sonnet",
                   help="Claude model alias or full ID (default: sonnet)")
    p.add_argument("--no-telegram",     action="store_true",
                   help="Print Claude output but skip Telegram posting")
    p.add_argument("--dry-run",         action="store_true",
                   help="Skip monitor run; analyse whatever is in today's dir")
    p.add_argument("--weekly-report",   action="store_true",
                   help="Post a 7-day outcomes precision digest to Telegram after the main run")
    return p.parse_args()


def main() -> int:
    _load_env()
    args = parse_args()

    # ── Step 1 ─────────────────────────────────────────────────────────────
    if args.dry_run:
        date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out_dir  = SCRIPT_DIR / "results" / "polywhaler" / date_str
        print(f"[dry-run] Using existing data in {out_dir}")
    else:
        out_dir = run_monitor(args)

    # ── Step 2 ─────────────────────────────────────────────────────────────
    prompt = build_prompt(out_dir)
    if not prompt:
        print("No results to analyse — exiting.")
        return 0

    # ── Step 3 ─────────────────────────────────────────────────────────────
    analysis = call_claude(prompt, args.model)

    print("\n--- Claude analysis ---")
    print(analysis)
    print("--- end ---\n")

    (out_dir / "claude_analysis.txt").write_text(analysis, encoding="utf-8")

    # ── Seed outcomes queue ────────────────────────────────────────────────
    outcomes_script = SCRIPT_DIR / "outcomes.py"
    if outcomes_script.exists():
        proc = subprocess.run(
            [sys.executable, str(outcomes_script), "seed", out_dir.name],
            capture_output=True, text=True,
        )
        if proc.stdout.strip():
            print(f"  {proc.stdout.strip()}")
        if proc.returncode != 0 and proc.stderr.strip():
            print(f"  Outcomes seed warning: {proc.stderr.strip()}", file=sys.stderr)

    # ── Seed watchlist portfolio ───────────────────────────────────────────
    portfolio_script = SCRIPT_DIR / "watchlist_portfolio.py"
    if portfolio_script.exists():
        proc = subprocess.run(
            [sys.executable, str(portfolio_script), "seed", out_dir.name],
            capture_output=True, text=True,
        )
        if proc.stdout.strip():
            print(f"  {proc.stdout.strip()}")
        if proc.returncode != 0 and proc.stderr.strip():
            print(f"  Portfolio seed warning: {proc.stderr.strip()}", file=sys.stderr)

    # ── Run health summary ─────────────────────────────────────────────────
    health = _health_summary(out_dir)
    print(f"\n{health}")

    # ── Step 4 ─────────────────────────────────────────────────────────────
    full_text = f"*Polymarket Insider Monitor — {out_dir.name}*\n\n{analysis}"

    if args.no_telegram:
        print("(--no-telegram set — skipping Telegram post)")
    else:
        token    = _require("TELEGRAM_BOT_TOKEN")
        chat_id  = _require("TELEGRAM_CHAT_ID")
        topic_id = os.environ.get("TELEGRAM_TOPIC_ID", "") or None

        post_telegram(full_text, token, chat_id, topic_id)

        # ── Weekly precision digest ────────────────────────────────────────
        if args.weekly_report and outcomes_script.exists():
            proc = subprocess.run(
                [sys.executable, str(outcomes_script), "report", "--days", "7"],
                capture_output=True, text=True,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                weekly_text = f"*Weekly precision digest — {out_dir.name}*\n\n{proc.stdout.strip()}"
                (out_dir / "weekly_digest.txt").write_text(weekly_text, encoding="utf-8")
                post_telegram(weekly_text, token, chat_id, topic_id)
            elif proc.stderr.strip():
                print(f"  Weekly digest warning: {proc.stderr.strip()}", file=sys.stderr)

    # ── Step 5: pipeline self-review ───────────────────────────────────────
    review = call_pipeline_review(full_text, out_dir, args.model)
    if review:
        review_file = out_dir / "pipeline_review.txt"
        review_file.write_text(review, encoding="utf-8")
        print(f"\n  Pipeline review saved → {review_file}")
        print("\n--- Pipeline review ---")
        print(review)
        print("--- end ---\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
