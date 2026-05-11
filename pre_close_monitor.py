#!/usr/bin/env python3
"""
pre_close_monitor.py — Alert on large trades in markets closing soon.

Fetches the polywhaler trade feed, filters for trades whose market endDate
falls within WINDOW_HOURS, and posts a Telegram alert for each new market
group with trades above MIN_SIZE_USD that haven't been reported yet.

Run frequently via cron (every 30 minutes recommended):
    */30 * * * * cd /home/kali/polymarket && /usr/bin/python3 pre_close_monitor.py >> /home/kali/polymarket/results/pre_close_monitor.log 2>&1

State: results/polywhaler/pre_close_state.json
         alerted hashes are retained for STATE_TTL_DAYS then pruned.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR     = Path(__file__).resolve().parent
STATE_FILE     = SCRIPT_DIR / "results" / "polywhaler" / "pre_close_state.json"
TRADES_URL     = "https://www.polywhaler.com/api/trades?category=all"
_UA            = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
_TG_BASE       = "https://api.telegram.org/bot{token}/{method}"

WINDOW_HOURS        = 4     # alert for markets closing within this many hours
MAX_TRADE_AGE_HOURS = 4    # ignore trades placed more than this many hours ago
MIN_SIZE_USD        = 10_000  # minimum trade size in USD to care about
STATE_TTL_DAYS      = 7    # prune alerted hashes older than this

# Polymarket categories to skip entirely — crypto price markets are noise.
CATEGORY_BLOCKLIST: frozenset[str] = frozenset({"crypto"})


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
# HTTP
# ---------------------------------------------------------------------------

def _get(url: str, retries: int = 3) -> dict | list:
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


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {"alerted": {}}


def save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(STATE_FILE)


# ---------------------------------------------------------------------------
# Trade feed
# ---------------------------------------------------------------------------

def fetch_trades(pages: int) -> list[dict]:
    trades: list[dict] = []
    seen: set[str] = set()
    for page in range(1, pages + 1):
        try:
            pg = _get(f"{TRADES_URL}&page={page}")
        except Exception as exc:
            print(f"  Page {page} error: {exc}", file=sys.stderr)
            break
        for t in pg.get("trades", []):
            h = t.get("transactionHash", "")
            if h and h not in seen:
                seen.add(h)
                trades.append(t)
        if not pg.get("hasNextPage"):
            break
    return trades


def hours_until_close(trade: dict, now: datetime) -> float | None:
    """Hours until this market's endDate, or None if past / missing."""
    raw = trade.get("endDate")
    if not raw:
        return None
    try:
        end_dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        h = (end_dt - now).total_seconds() / 3600
        return h if h > 0 else None
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Telegram
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
        if not resp.get("ok"):
            print(f"  Telegram error: {resp}", file=sys.stderr)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode()
        if exc.code == 400 and ("parse_mode" in body or "can't parse" in body.lower()):
            payload.pop("parse_mode")
            data = json.dumps(payload).encode()
            req2 = urllib.request.Request(url, data=data,
                                          headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req2, timeout=15) as r:
                resp = json.loads(r.read())
            if not resp.get("ok"):
                print(f"  Telegram error (plain-text retry): {resp}", file=sys.stderr)
        else:
            raise


def build_message(title: str, slug: str, hours_left: float, closes_at: datetime,
                  trades: list[dict], now: datetime) -> str:
    if hours_left < 1:
        time_str = f"{hours_left * 60:.0f}m"
    else:
        h = int(hours_left)
        m = int((hours_left - h) * 60)
        time_str = f"{h}h {m}m" if m else f"{h}h"

    close_str = closes_at.strftime("%b %-d %H:%M UTC")

    lines = [
        f"*Pre-close alert — closes in {time_str} ({close_str})*",
        f"*{_esc(title)}*",
        f"`{slug}`",
        "",
    ]

    for t in sorted(trades, key=lambda x: -(x.get("size") or 0)):
        name    = t.get("name") or (t.get("proxyWallet", "?")[:10] + "…")
        outcome = t.get("outcome", "?")
        size    = t.get("size") or 0
        pw      = t.get("insiderScore") or 0

        ts_raw = t.get("firstTradeTimestamp") or t.get("timestamp")
        if ts_raw:
            trade_dt = datetime.fromtimestamp(
                ts_raw / 1000 if ts_raw > 1e12 else float(ts_raw),
                tz=timezone.utc,
            )
            mins_ago = int((now - trade_dt).total_seconds() / 60)
            when = f"{mins_ago}m ago"
        else:
            when = ""

        parts = [f"• *{_esc(name)}*  {outcome}  ${size:,.0f}"]
        if pw:
            parts.append(f"pw={pw}")
        if when:
            parts.append(when)
        lines.append("  ".join(parts))

    return "\n".join(lines)


def _esc(s: str) -> str:
    """Escape Markdown special characters in a display string."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        s = s.replace(ch, f"\\{ch}")
    return s


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description="Alert on large trades near market close.")
    p.add_argument("--window",      type=float, default=WINDOW_HOURS,
                   help=f"Hours before close to start alerting (default: {WINDOW_HOURS})")
    p.add_argument("--max-trade-age", type=float, default=MAX_TRADE_AGE_HOURS,
                   help=f"Ignore trades older than this many hours (default: {MAX_TRADE_AGE_HOURS})")
    p.add_argument("--min-size",    type=float, default=MIN_SIZE_USD,
                   help=f"Minimum trade size USD (default: {MIN_SIZE_USD:,.0f})")
    p.add_argument("--pages",       type=int,   default=6,
                   help="Trade feed pages to fetch (default: 6)")
    p.add_argument("--no-telegram", action="store_true",
                   help="Print alerts to stdout instead of posting to Telegram")
    p.add_argument("--dry-run",     action="store_true",
                   help="Show what would be alerted without updating state")
    args = p.parse_args()

    _load_env()

    token    = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id  = os.environ.get("TELEGRAM_CHAT_ID", "")
    topic_id = os.environ.get("TELEGRAM_TOPIC_ID") or None

    if not args.no_telegram and not args.dry_run and (not token or not chat_id):
        print("Error: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID required in .env",
              file=sys.stderr)
        return 1

    now   = datetime.now(timezone.utc)
    state = load_state()

    # Prune stale alerted hashes
    cutoff = now.timestamp() - STATE_TTL_DAYS * 86400
    state["alerted"] = {h: ts for h, ts in state.get("alerted", {}).items()
                        if ts > cutoff}

    print(f"[{now.strftime('%Y-%m-%dT%H:%M')}Z] Fetching {args.pages} page(s)…")
    trades = fetch_trades(args.pages)
    print(f"  {len(trades)} unique trade(s) fetched")

    alerted_set = set(state["alerted"])
    max_age_secs = args.max_trade_age * 3600
    candidates: list[dict] = []
    skipped_stale = 0
    for t in trades:
        tx       = t.get("transactionHash", "")
        size     = t.get("size") or 0
        category = (t.get("category") or "").lower()
        if tx in alerted_set or size < args.min_size:
            continue
        if category in CATEGORY_BLOCKLIST:
            continue
        h = hours_until_close(t, now)
        if h is None or h > args.window:
            continue
        # Reject trades placed longer ago than max_trade_age — those are ordinary
        # positions that happen to be in a market closing soon, not late-breaking bets.
        ts_raw = t.get("firstTradeTimestamp") or t.get("timestamp")
        if ts_raw:
            trade_dt = datetime.fromtimestamp(
                ts_raw / 1000 if ts_raw > 1e12 else float(ts_raw),
                tz=timezone.utc,
            )
            age_secs = (now - trade_dt).total_seconds()
            if age_secs > max_age_secs:
                skipped_stale += 1
                continue
        t["_hours_left"] = h
        candidates.append(t)

    stale_note = f", {skipped_stale} stale (>{args.max_trade_age}h old)" if skipped_stale else ""
    print(f"  {len(candidates)} new candidate trade(s) within {args.window}h window "
          f"≥ ${args.min_size:,.0f}{stale_note}")

    if not candidates:
        return 0

    # Group by market slug for one alert per market
    by_slug: dict[str, list[dict]] = {}
    for t in candidates:
        slug = t.get("slug") or t.get("eventSlug") or "unknown"
        by_slug.setdefault(slug, []).append(t)

    print(f"  {len(by_slug)} market(s) to alert")

    for i, (slug, slug_trades) in enumerate(by_slug.items(), 1):
        title      = slug_trades[0].get("title", slug)
        hours_left = min(t["_hours_left"] for t in slug_trades)
        raw_end    = slug_trades[0].get("endDate", "")
        try:
            closes_at = datetime.fromisoformat(raw_end.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            closes_at = now
        msg = build_message(title, slug, hours_left, closes_at, slug_trades, now)

        if args.dry_run or args.no_telegram:
            print("\n" + "─" * 60)
            # Strip Markdown for readable terminal output
            plain = msg.replace("*", "").replace("`", "").replace("_", "")
            for ch in r"\_[]()~>#+-=|{}.!":
                plain = plain.replace(f"\\{ch}", ch)
            print(plain)
        else:
            try:
                _tg_send(token, chat_id, topic_id, msg)
                print(f"  [{i}/{len(by_slug)}] Sent: {title[:60]}")
            except Exception as exc:
                print(f"  [{i}/{len(by_slug)}] Failed ({title[:40]}): {exc}",
                      file=sys.stderr)
            if i < len(by_slug):
                time.sleep(0.5)

        if not args.dry_run:
            ts = now.timestamp()
            for t in slug_trades:
                tx = t.get("transactionHash", "")
                if tx:
                    state["alerted"][tx] = ts

    if not args.dry_run:
        save_state(state)

    print(f"Done. {len(by_slug)} market alert(s), "
          f"{len(candidates)} trade(s) added to state.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
