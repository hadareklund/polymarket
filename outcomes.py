#!/usr/bin/env python3
"""
outcomes.py — Ground truth feedback loop for polywhaler insider alerts.

Each daily run seeds pending records into results/outcomes.json.
Review them after markets resolve to build precision/recall metrics.

Verdicts:
  correct        — confirmed insider signal (timing + profile + bet won)
  false_positive — known noise (market maker, whale, bot, wrong call)
  ambiguous      — market unresolved, or genuinely unclear
  skip           — too small / not worth evaluating

Usage:
    python3 outcomes.py seed [YYYY-MM-DD]
    python3 outcomes.py pending [--min-score N]
    python3 outcomes.py review  [--min-score N]
    python3 outcomes.py tag <YYYY-MM-DD> <username> <verdict> [--note TEXT]
    python3 outcomes.py report  [--days N]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR    = Path(__file__).resolve().parent
OUTCOMES_FILE = SCRIPT_DIR / "results" / "outcomes.json"
RESULTS_DIR   = SCRIPT_DIR / "results" / "polywhaler"

VERDICTS = ("correct", "false_positive", "ambiguous", "skip")


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _load() -> list[dict]:
    if OUTCOMES_FILE.exists():
        try:
            return json.loads(OUTCOMES_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save(records: list[dict]) -> None:
    OUTCOMES_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTCOMES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(OUTCOMES_FILE)


def _make_id(date: str, username: str) -> str:
    return f"{date}:{username}"


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

def cmd_seed(args: argparse.Namespace) -> int:
    date_str = args.date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    analysis_file = RESULTS_DIR / date_str / "analysis.json"
    if not analysis_file.exists():
        print(f"No analysis.json for {date_str} ({analysis_file})", file=sys.stderr)
        return 1

    alerts  = json.loads(analysis_file.read_text(encoding="utf-8"))
    records = _load()
    existing_ids = {r["id"] for r in records}

    added = 0
    for a in alerts:
        username  = a.get("username", "")
        record_id = _make_id(date_str, username)
        if record_id in existing_ids:
            continue
        analytics = a.get("polymarket_analytics", {})
        records.append({
            "id":           record_id,
            "date":         date_str,
            "username":     username,
            "wallet":       analytics.get("wallet", ""),
            "market_title": a.get("market_title", ""),
            "bet":          a.get("outcome", ""),
            "trade_usd":    round(a.get("trade_size") or 0),
            "our_score":    a.get("our_score", 0),
            "pw_score":     a.get("polywhaler_insider_score", 0),
            "flag_types":   [f["type"] for f in a.get("flags", [])],
            "verdict":      "pending",
            "verdict_date": None,
            "note":         None,
        })
        added += 1

    _save(records)
    print(f"Seeded {added} new alert(s) for {date_str} ({len(records)} total in outcomes.json)")
    return 0


# ---------------------------------------------------------------------------
# pending
# ---------------------------------------------------------------------------

def cmd_pending(args: argparse.Namespace) -> int:
    records   = _load()
    min_score = getattr(args, "min_score", 0) or 0
    pending   = sorted(
        [r for r in records if r["verdict"] == "pending"
         and r.get("our_score", 0) >= min_score],
        key=lambda r: (-r.get("our_score", 0), r["date"]),
    )

    if not pending:
        print("No pending reviews" + (f" with score ≥ {min_score}" if min_score else "") + ".")
        return 0

    print(f"{len(pending)} pending alert(s):\n")
    for r in pending:
        print(
            f"  {r['date']}  {r['username']:<30s}"
            f"  score={r['our_score']:3d}  pw={r['pw_score']:3d}"
            f"  ${r['trade_usd']:>10,}  {r['market_title'][:45]}"
        )
    return 0


# ---------------------------------------------------------------------------
# review
# ---------------------------------------------------------------------------

def cmd_review(args: argparse.Namespace) -> int:
    records   = _load()
    min_score = getattr(args, "min_score", 0) or 0
    pending   = [
        r for r in records
        if r["verdict"] == "pending" and r.get("our_score", 0) >= min_score
    ]

    if not pending:
        print("No pending reviews" + (f" with score ≥ {min_score}" if min_score else "") + ".")
        return 0

    print(f"=== {len(pending)} pending review(s) ===\n")
    by_id   = {r["id"]: r for r in records}
    changed = 0

    for i, rec in enumerate(pending, 1):
        print(f"[{i}/{len(pending)}]  {rec['date']} — {rec['username']}")
        print(f"  Market:  {rec['market_title']}")
        print(
            f"  Bet:     {rec['bet']:<8}  "
            f"Size: ${rec['trade_usd']:,}  "
            f"Score: {rec['our_score']} (pw={rec['pw_score']})"
        )
        print(f"  Flags:   {', '.join(rec['flag_types'])}")
        if rec.get("wallet"):
            print(f"  Wallet:  {rec['wallet']}")
        print()

        while True:
            try:
                raw = input(
                    "  [c]orrect / [f]alse_positive / [a]mbiguous"
                    " / [s]kip / [n]ote / [q]uit: "
                ).strip().lower()
            except (EOFError, KeyboardInterrupt):
                print()
                _save(records)
                print(f"\nSaved {changed} verdict(s).")
                return 0

            if raw == "q":
                _save(records)
                print(f"\nSaved {changed} verdict(s).")
                return 0
            elif raw == "n":
                note = input("  Note: ").strip()
                by_id[rec["id"]]["note"] = note
                print(f"  Note saved.")
                continue
            elif raw in ("c", "f", "a", "s"):
                verdict = {
                    "c": "correct",
                    "f": "false_positive",
                    "a": "ambiguous",
                    "s": "skip",
                }[raw]
            else:
                print("  Invalid — use c / f / a / s / n / q.")
                continue

            try:
                note = input("  Note (optional, Enter to skip): ").strip()
            except (EOFError, KeyboardInterrupt):
                note = ""
            by_id[rec["id"]]["verdict"]      = verdict
            by_id[rec["id"]]["verdict_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if note:
                by_id[rec["id"]]["note"] = note
            changed += 1
            print(f"  → {verdict}\n")
            break

    _save(records)
    print(f"Review complete. {changed} verdict(s) saved.")
    return 0


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------

def cmd_tag(args: argparse.Namespace) -> int:
    if args.verdict not in VERDICTS:
        print(f"Invalid verdict '{args.verdict}'. Choose: {', '.join(VERDICTS)}", file=sys.stderr)
        return 1

    records   = _load()
    target_id = _make_id(args.date, args.username)

    for rec in records:
        if rec["id"] == target_id:
            rec["verdict"]      = args.verdict
            rec["verdict_date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if args.note:
                rec["note"] = args.note
            _save(records)
            print(f"Tagged {target_id} → {args.verdict}")
            return 0

    print(f"Alert not found: {target_id}", file=sys.stderr)
    matches = [r["username"] for r in records if r["date"] == args.date]
    if matches:
        print(f"Usernames for {args.date}: {', '.join(matches)}", file=sys.stderr)
    return 1


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    records = _load()
    days    = getattr(args, "days", 30) or 30
    cutoff  = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    recent  = [r for r in records if r["date"] >= cutoff]

    if not recent:
        print(f"No alerts in the last {days} days.")
        return 0

    total    = len(recent)
    pending  = sum(1 for r in recent if r["verdict"] == "pending")
    reviewed = total - pending
    correct  = sum(1 for r in recent if r["verdict"] == "correct")
    fp       = sum(1 for r in recent if r["verdict"] == "false_positive")
    ambig    = sum(1 for r in recent if r["verdict"] == "ambiguous")
    skipped  = sum(1 for r in recent if r["verdict"] == "skip")

    print(f"=== Outcome Report (last {days} days) ===\n")
    print(f"Total alerts:     {total}")
    if total:
        print(f"Reviewed:         {reviewed} ({reviewed / total:.0%})")
    print(f"Pending:          {pending}")
    print()

    decided = correct + fp + ambig
    if decided > 0:
        precision = correct / decided
        print(f"Correct:          {correct}  ({precision:.0%} precision)")
        print(f"False positive:   {fp}")
        print(f"Ambiguous:        {ambig}")
        if skipped:
            print(f"Skipped:          {skipped}")
        print()

        # Precision by flag type
        flag_stats: dict[str, list[int]] = defaultdict(lambda: [0, 0])
        for r in recent:
            if r["verdict"] in ("correct", "false_positive"):
                for flag in r.get("flag_types", []):
                    flag_stats[flag][1] += 1
                    if r["verdict"] == "correct":
                        flag_stats[flag][0] += 1

        if flag_stats:
            print("Precision by flag type (correct / decided):")
            for flag, (c, t) in sorted(flag_stats.items(), key=lambda x: -x[1][1]):
                pct = c / t if t else 0
                bar = "█" * c + "░" * (t - c)
                print(f"  {flag:<38s}  {c:2d}/{t:<2d}  {pct:.0%}  {bar}")
    else:
        print("No decided verdicts yet — run `review` to tag some alerts.")

    return 0


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    p   = argparse.ArgumentParser(description="Ground truth feedback for polywhaler alerts.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Load alerts from analysis.json into outcomes.json")
    p_seed.add_argument("date", nargs="?", help="YYYY-MM-DD (default: today)")

    p_pend = sub.add_parser("pending", help="List unreviewed alerts")
    p_pend.add_argument("--min-score", type=int, default=0)

    p_rev = sub.add_parser("review", help="Interactively tag pending alerts")
    p_rev.add_argument("--min-score", type=int, default=0)

    p_tag = sub.add_parser("tag", help="Tag a single alert non-interactively")
    p_tag.add_argument("date")
    p_tag.add_argument("username")
    p_tag.add_argument("verdict", choices=VERDICTS)
    p_tag.add_argument("--note", default="")

    p_rep = sub.add_parser("report", help="Precision/recall statistics")
    p_rep.add_argument("--days", type=int, default=30, help="Lookback window (default: 30)")

    args = p.parse_args()
    return {"seed": cmd_seed, "pending": cmd_pending, "review": cmd_review,
            "tag": cmd_tag, "report": cmd_report}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
