#!/usr/bin/env python3
"""Falcon API client for Polymarket on-chain trader analytics.

Agents used:
  586 — Lifetime Performance  (total_pnl, roi, total_trades, avg_trade_size)
  581 — Wallet 360            (60+ behavioral/risk metrics over a rolling window)
  579 — Top Traders           (leaderboard rank and ROI for a specific wallet)
  584 — Falcon Leaderboard    (h_score / tier when wallet is ranked)
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
    """Return overall lifetime trading stats for a wallet (agent 586)."""
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
    """Fetch analytics for a wallet from both Falcon and Polymarket's own API.

    Polymarket positions data replaces Falcon's lifetime_performance (agent 586),
    which was found to report systematically inflated PnL figures. Falcon's
    wallet_360 (agent 581) is retained for win_rate, sharpe, and diversity metrics.
    """
    result: dict = {}

    # Polymarket positions API — authoritative portfolio/P&L data
    try:
        stats = polymarket_api.wallet_stats(wallet)
        if stats:
            result["positions_data"] = stats
    except Exception as exc:
        print(f"  polymarket_api: {wallet[:10]}… error — {exc}", file=sys.stderr)

    # Falcon wallet_360 — behavioral/risk metrics (win_rate, sharpe, diversity)
    w360 = wallet_360(wallet, token, window_days=30)
    if w360:
        result["wallet_360_30d"] = w360

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
