#!/usr/bin/env python3
"""
watchlist_portfolio.py — Paper portfolio tracking the pipeline's flagged trades.

Seeds one $100 paper bet per flagged trader from each daily analysis.json run.
Tracks P&L as markets resolve via the Gamma API, and posts a weekly performance
report to Telegram so the operator can see whether the pipeline's calls make money.

Usage:
    python3 watchlist_portfolio.py seed [YYYY-MM-DD]   # seed from analysis.json
    python3 watchlist_portfolio.py update               # refresh prices & resolutions
    python3 watchlist_portfolio.py report [--days N]   # print P&L report
    python3 watchlist_portfolio.py weekly               # update + report + Telegram

Scheduled weekly via cron (every Monday 09:00 UTC):
    0 9 * * 1 cd /home/kali/polymarket && /usr/bin/python3 watchlist_portfolio.py weekly >> /home/kali/polymarket/results/watchlist_portfolio.log 2>&1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT_DIR     = Path(__file__).resolve().parent
PORTFOLIO_FILE = SCRIPT_DIR / "results" / "watchlist_portfolio.json"
RESULTS_DIR    = SCRIPT_DIR / "results" / "polywhaler"
_GAMMA_BASE    = "https://gamma-api.polymarket.com"
_TG_BASE       = "https://api.telegram.org/bot{token}/{method}"
_UA            = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"

PAPER_STAKE = 100.0  # virtual $ per seeded trade
MIN_SCORE   = 5      # minimum our_score to include in portfolio


# ---------------------------------------------------------------------------
# Env
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


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _load_portfolio() -> list[dict]:
    if PORTFOLIO_FILE.exists():
        try:
            return json.loads(PORTFOLIO_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return []


def _save_portfolio(positions: list[dict]) -> None:
    PORTFOLIO_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = PORTFOLIO_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(positions, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(PORTFOLIO_FILE)


# ---------------------------------------------------------------------------
# Gamma API
# ---------------------------------------------------------------------------

def _gamma_get(slug: str) -> dict | None:
    url = f"{_GAMMA_BASE}/markets?slug={slug}"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
            return data[0] if isinstance(data, list) and data else None
    except Exception:
        return None


def _parse_market(market: dict, target_outcome: str) -> tuple[float | None, str]:
    """Return (current_price, status).

    status is one of: 'open', 'won', 'lost', 'ambiguous'
    current_price is the price of the target outcome token (0–1).
    """
    raw_prices = market.get("outcomePrices", [])
    outcomes   = market.get("outcomes", [])
    if isinstance(raw_prices, str):
        try:
            raw_prices = json.loads(raw_prices)
        except Exception:
            return None, "open"
    if isinstance(outcomes, str):
        try:
            outcomes = json.loads(outcomes)
        except Exception:
            return None, "open"
    if not raw_prices or not outcomes or len(raw_prices) != len(outcomes):
        return None, "open"

    prices = [float(p) for p in raw_prices]

    target_idx = next(
        (i for i, o in enumerate(outcomes) if o.lower() == target_outcome.lower()),
        None,
    )
    if target_idx is None:
        return None, "open"

    current_price = prices[target_idx]

    if not market.get("closed"):
        return current_price, "open"

    max_price = max(prices)
    if max_price < 0.9:
        return current_price, "ambiguous"

    winner_idx = prices.index(max_price)
    won = winner_idx == target_idx
    return (1.0 if won else 0.0), ("won" if won else "lost")


# ---------------------------------------------------------------------------
# P&L
# ---------------------------------------------------------------------------

def _pnl(entry_price: float, current_price: float, stake: float = PAPER_STAKE) -> float:
    """Dollar P&L: value of position minus cost."""
    if entry_price <= 0:
        return 0.0
    shares = stake / entry_price
    return round(shares * current_price - stake, 2)


def _pnl_pct(entry_price: float, current_price: float) -> float:
    if entry_price <= 0:
        return 0.0
    return round((current_price / entry_price - 1) * 100, 1)


# ---------------------------------------------------------------------------
# seed
# ---------------------------------------------------------------------------

def cmd_seed(args: argparse.Namespace) -> int:
    date_str = getattr(args, "date", None) or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    day_dir  = RESULTS_DIR / date_str

    analysis_file = day_dir / "analysis.json"
    trades_file   = day_dir / "trades.json"

    if not analysis_file.exists():
        print(f"No analysis.json for {date_str}", file=sys.stderr)
        return 1

    alerts = json.loads(analysis_file.read_text(encoding="utf-8"))

    # Build (username, title) → (slug, price) from trades.json
    slug_map: dict[tuple[str, str], tuple[str, float]] = {}
    if trades_file.exists():
        try:
            for t in json.loads(trades_file.read_text(encoding="utf-8")):
                uname = (t.get("name") or t.get("pseudonym") or "").strip()
                title = (t.get("title") or "").strip()
                slug  = (t.get("slug") or "").strip()
                price = float(t.get("price") or 0)
                if uname and title and slug and price > 0:
                    key = (uname, title)
                    if key not in slug_map or price > slug_map[key][1]:
                        slug_map[key] = (slug, price)
        except Exception as exc:
            print(f"Warning: could not read trades.json: {exc}", file=sys.stderr)

    positions    = _load_portfolio()
    existing_ids = {p["id"] for p in positions}
    added        = 0
    skipped      = 0

    for alert in alerts:
        username = alert.get("username", "")
        score    = alert.get("our_score", 0)

        if score < MIN_SCORE:
            skipped += 1
            continue

        rec_id = f"{date_str}:{username}"
        if rec_id in existing_ids:
            continue

        title   = alert.get("market_title", "")
        outcome = alert.get("outcome", "")

        # Look up slug + entry price from trades.json
        slug, entry_price = slug_map.get((username, title), ("", 0.0))
        if not slug:
            # Fallback: match by username alone
            for (u, _), (s, p) in slug_map.items():
                if u == username and p > 0:
                    slug, entry_price = s, p
                    break

        positions.append({
            "id":             rec_id,
            "date_flagged":   date_str,
            "username":       username,
            "market_title":   title,
            "market_slug":    slug,
            "outcome":        outcome,
            "entry_price":    entry_price,
            "trade_size_usd": round(alert.get("trade_size") or 0),
            "our_score":      score,
            "pw_score":       alert.get("polywhaler_insider_score", 0),
            "paper_stake":    PAPER_STAKE,
            "status":         "open",
            "current_price":  entry_price or None,
            "pnl_usd":        0.0,
            "pnl_pct":        0.0,
            "last_updated":   None,
        })
        existing_ids.add(rec_id)
        added += 1

    _save_portfolio(positions)
    note = f" (skipped {skipped} below score {MIN_SCORE})" if skipped else ""
    print(f"Seeded {added} new position(s) for {date_str}{note} ({len(positions)} total)")
    return 0


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def cmd_update(_args: argparse.Namespace) -> int:
    positions = _load_portfolio()
    open_pos  = [p for p in positions if p["status"] == "open" and p.get("market_slug")]

    if not open_pos:
        print("No open positions to update.")
        return 0

    now      = datetime.now(timezone.utc).isoformat()
    slugs    = list({p["market_slug"] for p in open_pos})
    print(f"Fetching {len(slugs)} market(s) from Gamma API…")

    slug_cache: dict[str, dict | None] = {}
    for i, slug in enumerate(slugs, 1):
        slug_cache[slug] = _gamma_get(slug)
        if i % 10 == 0:
            time.sleep(0.3)

    updated  = 0
    resolved = 0

    for pos in open_pos:
        market = slug_cache.get(pos["market_slug"])
        if not market:
            continue

        entry   = pos.get("entry_price") or 0
        outcome = pos.get("outcome", "")

        current_price, status = _parse_market(market, outcome)
        if current_price is None:
            continue

        pos["current_price"] = current_price
        pos["last_updated"]  = now
        if entry > 0:
            pos["pnl_usd"] = _pnl(entry, current_price)
            pos["pnl_pct"] = _pnl_pct(entry, current_price)

        if status in ("won", "lost", "ambiguous"):
            pos["status"] = status
            resolved += 1

        updated += 1

    _save_portfolio(positions)
    msg = f"Updated {updated} position(s)"
    if resolved:
        msg += f", {resolved} newly resolved"
    print(msg)
    return 0


# ---------------------------------------------------------------------------
# report formatting
# ---------------------------------------------------------------------------

def _build_report(positions: list[dict], days: int, for_telegram: bool = False) -> str:
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff  = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    recent  = [p for p in positions if p["date_flagged"] >= cutoff]

    if not recent:
        return f"No positions flagged in the last {days} days."

    open_n  = sum(1 for p in recent if p["status"] == "open")
    won_n   = sum(1 for p in recent if p["status"] == "won")
    lost_n  = sum(1 for p in recent if p["status"] == "lost")
    ambig_n = sum(1 for p in recent if p["status"] == "ambiguous")
    decided = won_n + lost_n

    # P&L only on positions with a known entry price
    priced  = [p for p in recent if (p.get("entry_price") or 0) > 0
               and p["status"] in ("won", "lost")]
    total_pnl    = sum(p.get("pnl_usd", 0) for p in priced)
    total_staked = sum(p.get("paper_stake", PAPER_STAKE) for p in priced)
    pnl_pct_str  = f" ({'+' if total_pnl >= 0 else ''}{total_pnl / total_staked * 100:.1f}%)" \
                   if total_staked > 0 else ""
    win_rate_str = f"{won_n / decided:.0%}" if decided > 0 else "n/a"

    lines: list[str] = []

    if for_telegram:
        lines.append(f"*Portfolio Watch — {now_str}*")
    else:
        lines.append(f"=== Portfolio Report — {now_str} (last {days} days) ===")
    lines.append("")

    status_parts = [f"open={open_n}", f"won={won_n}", f"lost={lost_n}"]
    if ambig_n:
        status_parts.append(f"ambig={ambig_n}")
    lines.append(f"Positions:  {len(recent)}  ({', '.join(status_parts)})")
    lines.append(f"Win rate:   {win_rate_str}  ({won_n}/{decided} decided)")
    lines.append("")

    sign = "+" if total_pnl >= 0 else ""
    lines.append(f"Paper P&L:  {sign}${total_pnl:,.0f}{pnl_pct_str}  [${PAPER_STAKE:.0f}/trade × {len(priced)} trades]")

    # All-time stats if days < 999
    all_priced = [p for p in positions if (p.get("entry_price") or 0) > 0
                  and p["status"] in ("won", "lost")]
    if len(all_priced) > len(priced):
        all_pnl    = sum(p.get("pnl_usd", 0) for p in all_priced)
        all_staked = sum(p.get("paper_stake", PAPER_STAKE) for p in all_priced)
        all_won    = sum(1 for p in positions if p["status"] == "won")
        all_dec    = sum(1 for p in positions if p["status"] in ("won", "lost"))
        all_sign   = "+" if all_pnl >= 0 else ""
        all_wr     = f"{all_won / all_dec:.0%}" if all_dec > 0 else "n/a"
        all_pct    = f" ({all_sign}{all_pnl / all_staked * 100:.1f}%)" if all_staked > 0 else ""
        lines.append(f"All-time:   {all_sign}${all_pnl:,.0f}{all_pct}  win={all_wr}  ({all_dec} decided)")

    # Resolved positions this period
    resolved = sorted(
        [p for p in recent if p["status"] in ("won", "lost")],
        key=lambda x: -(x.get("pnl_usd") or 0),
    )
    if resolved:
        lines.append("")
        lines.append("*Resolved trades:*" if for_telegram else "Resolved trades:")
        for p in resolved[:12]:
            pnl  = p.get("pnl_usd", 0) or 0
            sign = "+" if pnl >= 0 else ""
            mark = "+" if pnl >= 0 else "-"
            title = p["market_title"][:38]
            lines.append(
                f"  [{mark}] {p['username']:<18s}  {p['outcome']:<3s}  "
                f"{title:<38s}  {sign}${abs(pnl):>6,.0f}"
            )

    # Top open positions
    top_open = sorted(
        [p for p in recent if p["status"] == "open"],
        key=lambda x: -x.get("our_score", 0),
    )[:5]
    if top_open:
        lines.append("")
        lines.append("*Top open positions:*" if for_telegram else "Top open positions:")
        for p in top_open:
            cp       = p.get("current_price")
            ep       = p.get("entry_price") or 0
            price_s  = f"@ {cp:.2f}" if cp is not None else "(no price)"
            pnl_open = _pnl(ep, cp) if (cp is not None and ep > 0) else 0
            pnl_s    = f"  P&L {'+' if pnl_open >= 0 else ''}${pnl_open:,.0f}" if ep > 0 else ""
            lines.append(
                f"  * {p['username']:<18s}  {p['outcome']:<3s}  "
                f"{p['market_title'][:36]}  {price_s}  score={p['our_score']}{pnl_s}"
            )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

def cmd_report(args: argparse.Namespace) -> int:
    positions = _load_portfolio()
    days      = getattr(args, "days", 30) or 30
    print(_build_report(positions, days))
    return 0


# ---------------------------------------------------------------------------
# weekly
# ---------------------------------------------------------------------------

def _tg_send(token: str, chat_id: str, topic_id: str | None, text: str) -> None:
    payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if topic_id:
        payload["message_thread_id"] = int(topic_id)
    url  = _TG_BASE.format(token=token, method="sendMessage")
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data,
                                  headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read())
        if resp.get("ok"):
            return
        print(f"Telegram error: {resp}", file=sys.stderr)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if exc.code == 400 and ("parse_mode" in body or "can't parse" in body.lower()):
            payload.pop("parse_mode")
            data = json.dumps(payload).encode()
            req2 = urllib.request.Request(url, data=data,
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req2, timeout=15) as r2:
                resp = json.loads(r2.read())
            if not resp.get("ok"):
                print(f"Telegram error (plain retry): {resp}", file=sys.stderr)
        else:
            raise


def cmd_weekly(_args: argparse.Namespace) -> int:
    print("Updating positions…")
    cmd_update(argparse.Namespace())

    positions = _load_portfolio()
    report    = _build_report(positions, days=7, for_telegram=True)

    print("\n" + report + "\n")

    _load_env()
    token    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id  = os.environ.get("TELEGRAM_CHAT_ID", "")
    topic_id = os.environ.get("TELEGRAM_TOPIC_ID") or None

    if not token or not chat_id:
        print("No Telegram credentials — skipping post.", file=sys.stderr)
        return 0

    log_path = SCRIPT_DIR / "results" / "watchlist_portfolio_weekly.txt"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(report, encoding="utf-8")

    try:
        _tg_send(token, chat_id, topic_id, report)
        print("Telegram weekly report sent.")
    except Exception as exc:
        print(f"Telegram error: {exc}", file=sys.stderr)
        return 1

    return 0


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> int:
    _load_env()
    p   = argparse.ArgumentParser(
        description="Paper portfolio tracker for polywhaler pipeline recommendations."
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    p_seed = sub.add_parser("seed", help="Seed positions from analysis.json")
    p_seed.add_argument("date", nargs="?", help="YYYY-MM-DD (default: today)")

    sub.add_parser("update", help="Refresh prices and check for resolved markets")

    p_rep = sub.add_parser("report", help="Print portfolio P&L report")
    p_rep.add_argument("--days", type=int, default=30, help="Lookback window (default: 30)")

    sub.add_parser("weekly", help="Update prices, generate report, post to Telegram")

    args = p.parse_args()
    return {"seed": cmd_seed, "update": cmd_update,
            "report": cmd_report, "weekly": cmd_weekly}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
