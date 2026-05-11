#!/usr/bin/env python3
"""Falcon API client for Polymarket on-chain trader analytics.

Agents used:
  569 — Profit & Loss         (net REALIZED pnl from settled markets, wins/losses/win_rate)
  581 — Wallet 360            (60+ behavioral/risk metrics: sharpe, diversity, sybil_risk_score)
  579 — Top Traders           (leaderboard rank and ROI for a specific wallet)
  584 — Falcon Leaderboard    (h_score / tier when wallet is ranked)

Agent 586 (Lifetime Performance) was removed — its total_pnl field did not account for
open-position losses and produced systematically inflated figures. Agent 569 is used
instead, which explicitly returns net realized PnL from settled markets only.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import polymarket_api

CACHE_MAX_AGE_HOURS = 24

FALCON_URL = "https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized"

# Fields from Wallet 360 that are most useful for OSINT context.
_W360_KEEP = {
    "annualized_return", "avg_market_exposure", "avg_trade_size",
    "best_market_pnl", "buy_trade_ratio", "calculation_window_days",
    "calmar_ratio", "category_diversity_score", "combined_risk_score",
    "days_active", "dominant_category", "drawdown_from_peak",
    "hit_rate", "kelly_fraction", "largest_loss", "largest_win",
    "leverage_ratio", "loss_rate", "market_count", "max_drawdown",
    "net_pnl", "peak_net_pnl", "realized_pnl", "roi_pct",
    "sharpe_ratio", "sortino_ratio", "total_invested",
    "total_trades", "unique_markets_traded", "win_rate",
    "worst_market_pnl",
    # Risk / Sybil signals (added after doc review)
    "sybil_risk_score", "risk_level",
}


class _RateLimiter:
    def __init__(self, rate: float = 4.0):
        self._interval = 1.0 / rate
        self._lock = threading.Lock()
        self._next_slot = time.monotonic()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            if now >= self._next_slot:
                self._next_slot = now + self._interval
                return
            wait_until = self._next_slot
            self._next_slot += self._interval
        time.sleep(max(0.0, wait_until - time.monotonic()))


_limiter = _RateLimiter(rate=4.0)


def _call(token: str, payload: dict, timeout: int = 20) -> dict | None:
    _limiter.acquire()
    params = payload.get("params", {})
    wallet = params.get("wallet_address") or params.get("proxy_wallet") or "?"
    label  = f"agent={payload.get('agent_id', '?')} wallet={wallet}"

    body = json.dumps(payload).encode()
    req  = Request(FALCON_URL, data=body, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    })
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
    except HTTPError as exc:
        try:
            data = json.loads(exc.read())
        except Exception:
            print(f"Falcon {label}: HTTP {exc.code}", file=sys.stderr)
            return None
    except TimeoutError:
        print(f"Falcon {label}: timed out after {timeout}s", file=sys.stderr)
        return None
    except (URLError, OSError) as exc:
        print(f"Falcon {label}: network error — {exc}", file=sys.stderr)
        return None

    if data.get("status") == "error" or data.get("error"):
        msg = data.get("message") or data.get("error") or "unknown error"
        print(f"Falcon {label}: API error — {msg}", file=sys.stderr)
        return None
    results = (data.get("data") or {}).get("results") or []
    return results[0] if results else None


def lifetime_performance(wallet: str, token: str) -> dict | None:
    """Return overall lifetime trading stats for a wallet (agent 586).

    Deprecated: agent 586's total_pnl does not correctly account for open-position
    losses. Use realized_pnl() (agent 569) instead for accurate figures.
    Kept for backward compatibility with existing cached profiles.
    """
    raw = _call(token, {
        "agent_id": 586,
        "params": {"wallet_address": wallet},
        "formatter_config": {"format_type": "raw"},
    })
    if not raw:
        return None
    return {
        "total_pnl": raw.get("total_pnl"),
        "roi_pct": raw.get("roi_pct"),
        "total_trades": raw.get("total_trades"),
        "avg_trade_size": raw.get("avg_trade_size"),
        "total_invested": raw.get("total_invested"),
        "avg_pnl_per_trade": raw.get("avg_pnl_per_trade"),
        "last_updated": raw.get("last_updated"),
    }


def realized_pnl(wallet: str, token: str) -> dict | None:
    """Return net realized PnL from settled markets for a wallet (agent 569).

    Agent 569 explicitly returns 'net realized profit and loss — only realized
    gains from confirmed trades or settled markets are included.' This is the
    correct source for historical accuracy signals.

    Uses granularity='all' to get a single all-time aggregate result.
    """
    raw = _call(token, {
        "agent_id": 569,
        "params": {
            "wallet":      wallet,
            "granularity": "all",
            "start_time":  "2022-01-01",
            "end_time":    datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        },
        "formatter_config": {"format_type": "raw"},
    })
    if not raw:
        return None
    try:
        pnl      = float(raw.get("pnl")      or 0)
        trades   = int(raw.get("trades")     or 0)
        wins     = int(raw.get("wins")       or 0)
        losses   = int(raw.get("losses")     or 0)
        invested = float(raw.get("invested") or 0)
        # Agent 569 returns win_rate on a 0–100 scale; normalise to 0–1
        raw_wr   = raw.get("win_rate")
        win_rate = (float(raw_wr) / 100.0) if raw_wr is not None \
                   else (wins / trades if trades > 0 else 0.0)
    except (TypeError, ValueError):
        return None
    return {
        "pnl":      round(pnl, 2),
        "trades":   trades,
        "wins":     wins,
        "losses":   losses,
        "win_rate": round(win_rate, 4),
        "invested": round(invested, 2),
    }


def wallet_360(wallet: str, token: str, window_days: int = 30) -> dict | None:
    """Return behavioral/risk metrics for a wallet over a rolling window (agent 581).

    Falls back to 7-day window if 30-day has no data.
    """
    for days in ([window_days] if window_days == 7 else [window_days, 7]):
        raw = _call(token, {
            "agent_id": 581,
            "params": {"proxy_wallet": wallet, "window_days": str(days)},
            "formatter_config": {"format_type": "raw"},
        })
        if raw:
            result = {k: v for k, v in raw.items() if k in _W360_KEEP}
            if result:
                result["window_days"] = days
                return result
    return None


def leaderboard_rank(wallet: str, token: str, period: str = "7d") -> dict | None:
    """Return leaderboard position for a wallet (agent 579), or None if not ranked."""
    raw = _call(token, {
        "agent_id": 579,
        "params": {"wallet_address": wallet, "leaderboard_period": period},
        "pagination": {"limit": 50, "offset": 0},
        "formatter_config": {"format_type": "raw"},
    })
    if not raw:
        return None
    # Results contain rank/address/pnl. Find the wallet's entry.
    if isinstance(raw, dict) and raw.get("address", "").lower() == wallet.lower():
        return {
            "period": period,
            "rank": raw.get("rank"),
            "total_pnl": raw.get("total_pnl"),
            "roi": raw.get("roi"),
            "win_rate": raw.get("win_rate"),
            "sharpe_ratio": raw.get("sharpe_ratio"),
        }
    return None


def falcon_score(wallet: str, token: str) -> dict | None:
    """Return Falcon h_score and tier for a wallet (agent 584)."""
    raw = _call(token, {
        "agent_id": 584,
        "params": {"wallet_address": wallet},
        "pagination": {"limit": 10, "offset": 0},
        "formatter_config": {"format_type": "raw"},
    })
    if not raw:
        return None
    # Leaderboard may return multiple entries; find matching wallet.
    if isinstance(raw, dict):
        candidates = [raw]
    else:
        return None
    for entry in candidates:
        if entry.get("wallet", "").lower() == wallet.lower():
            return {
                "h_score": entry.get("h_score"),
                "tier": entry.get("tier"),
                "leaderboard_rank": entry.get("leaderboard_rank"),
                "roi_pct_15d": entry.get("roi_pct_15d"),
                "win_rate_pct_15d": entry.get("win_rate_pct_15d"),
                "total_pnl_15d": entry.get("total_pnl_15d"),
                "sharpe_ratio_15d": entry.get("sharpe_ratio_15d"),
                "total_trades_15d": entry.get("total_trades_15d"),
            }
    return None


def is_fresh(profile: dict, max_age_hours: int = CACHE_MAX_AGE_HOURS) -> bool:
    """Return True if polymarket_analytics in profile was fetched within max_age_hours."""
    fetched_at = (profile.get("polymarket_analytics") or {}).get("fetched_at")
    if not fetched_at:
        return False
    try:
        ts = datetime.fromisoformat(fetched_at)
        return (datetime.now(timezone.utc) - ts).total_seconds() < max_age_hours * 3600
    except (ValueError, TypeError):
        return False


def enrich_wallet(wallet: str, token: str) -> dict:
    """Fetch analytics for a wallet from Falcon (agents 569, 581) and Polymarket API.

    Three complementary sources:
      realized_performance  — agent 569: net realized PnL from settled markets,
                              wins/losses/win_rate. The authoritative historical
                              accuracy signal.
      wallet_360_30d        — agent 581: sharpe, diversity, sybil_risk_score,
                              and other rolling behavioral metrics.
      positions_data        — Polymarket API: current portfolio value and open
                              position breakdown. Sophistication/scale signal.
    """
    result: dict = {}

    # Agent 569: net realized PnL from settled markets
    rp = realized_pnl(wallet, token)
    if rp:
        result["realized_performance"] = rp

    # Agent 581: behavioral/risk metrics
    w360 = wallet_360(wallet, token, window_days=30)
    if w360:
        result["wallet_360_30d"] = w360

    # Polymarket positions API: current portfolio
    try:
        stats = polymarket_api.wallet_stats(wallet)
        if stats:
            result["positions_data"] = stats
    except Exception as exc:
        print(f"  polymarket_api: {wallet[:10]}… error — {exc}", file=sys.stderr)

    if result:
        result["fetched_at"] = datetime.now(timezone.utc).isoformat()
    return result


def load_token(env_var: str = "FALCON_API_TOKEN") -> str | None:
    """Read Falcon token from env or .env file."""
    token = os.environ.get(env_var)
    if token:
        return token
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{env_var}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None
