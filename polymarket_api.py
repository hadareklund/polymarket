#!/usr/bin/env python3
"""Polymarket Data API client — portfolio and position metrics.

Replaces Falcon's unreliable lifetime_performance (agent 586) with
data sourced directly from Polymarket's own data API.

Key endpoints used:
  /positions?user=<wallet>  — open positions with per-position P&L
  /value?user=<wallet>      — current mark-to-market portfolio value
"""
from __future__ import annotations

import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

_BASE = "https://data-api.polymarket.com"
_UA   = "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0"
_POSITIONS_PAGE = 100


def _get(path: str, timeout: int = 15) -> list | dict | None:
    url = f"{_BASE}{path}"
    req = Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    except HTTPError as e:
        if e.code == 404:
            return None
        raise
    except (URLError, OSError):
        return None


def fetch_positions(wallet: str) -> list[dict]:
    """Return all open positions for a wallet, paginating as needed."""
    wallet = wallet.lower()
    all_pos: list[dict] = []
    offset = 0
    while True:
        data = _get(f"/positions?user={wallet}&limit={_POSITIONS_PAGE}&offset={offset}")
        if not data:
            break
        all_pos.extend(data)
        if len(data) < _POSITIONS_PAGE:
            break
        offset += len(data)
        time.sleep(0.15)
    return all_pos


def fetch_portfolio_value(wallet: str) -> float:
    """Return current mark-to-market portfolio value (0.0 if unavailable)."""
    data = _get(f"/value?user={wallet.lower()}")
    if data and isinstance(data, list) and data:
        try:
            return float(data[0].get("value") or 0)
        except (TypeError, ValueError):
            pass
    return 0.0


def wallet_stats(wallet: str) -> dict:
    """Fetch and derive portfolio metrics for a wallet from Polymarket's API.

    Returns a dict with:
      portfolio_value       current mark-to-market of all open positions
      open_positions        number of open bets
      cash_pnl              sum of unrealized P&L on open positions
                            (currentValue - initialValue per position)
      realized_pnl          sum of realized P&L from partial sells on
                            still-open positions
      total_bought          total USDC ever spent acquiring current open positions
      top_position_value    current value of the largest single position
      top_position_title    market title of the largest position
      top_position_pct      largest position as fraction of portfolio_value
    """
    positions = fetch_positions(wallet)
    portfolio_value = fetch_portfolio_value(wallet)

    if not positions:
        return {
            "portfolio_value": portfolio_value,
            "open_positions": 0,
            "cash_pnl": 0.0,
            "realized_pnl": 0.0,
            "total_bought": 0.0,
            "top_position_value": 0.0,
            "top_position_title": "",
            "top_position_pct": 0.0,
        }

    cash_pnl     = sum(float(p.get("cashPnl")     or 0) for p in positions)
    realized_pnl = sum(float(p.get("realizedPnl") or 0) for p in positions)
    total_bought = sum(float(p.get("totalBought") or 0) for p in positions)

    top = max(positions, key=lambda p: float(p.get("currentValue") or 0))
    top_value = float(top.get("currentValue") or 0)
    top_pct   = (top_value / portfolio_value) if portfolio_value > 0 else 0.0

    return {
        "portfolio_value":    round(portfolio_value, 2),
        "open_positions":     len(positions),
        "cash_pnl":           round(cash_pnl, 2),
        "realized_pnl":       round(realized_pnl, 2),
        "total_bought":       round(total_bought, 2),
        "top_position_value": round(top_value, 2),
        "top_position_title": top.get("title", ""),
        "top_position_pct":   round(top_pct, 4),
    }
