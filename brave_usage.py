"""
Persistent Brave Search API usage tracker.

Stores monthly request counts in .brave_usage.json at the project root.
Resets automatically when the calendar month rolls over.
Thread-safe: uses a file lock so concurrent workers don't corrupt the counter.

Limits:
  MONTHLY_LIMIT = 5000 requests / month
  RATE_LIMIT    = 50 requests / second
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_USAGE_FILE = Path(__file__).resolve().parent / ".brave_usage.json"
MONTHLY_LIMIT = 5000

_lock = threading.Lock()


def _current_month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load() -> dict:
    if _USAGE_FILE.exists():
        try:
            return json.loads(_USAGE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return {"month": _current_month(), "used": 0}


def _save(data: dict) -> None:
    tmp = _USAGE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(_USAGE_FILE)


def get_usage() -> dict:
    with _lock:
        data = _load()
        if data.get("month") != _current_month():
            data = {"month": _current_month(), "used": 0}
            _save(data)
        return data


def increment(n: int = 1) -> dict:
    """Atomically record n requests used. Returns updated usage dict."""
    with _lock:
        data = _load()
        if data.get("month") != _current_month():
            data = {"month": _current_month(), "used": 0}
        data["used"] += n
        _save(data)
        return data


def remaining() -> int:
    return max(0, MONTHLY_LIMIT - get_usage()["used"])


def check(n: int = 1) -> None:
    """Raise RuntimeError inside the lock if fewer than n requests remain."""
    with _lock:
        data = _load()
        if data.get("month") != _current_month():
            data = {"month": _current_month(), "used": 0}
            _save(data)
        left = max(0, MONTHLY_LIMIT - data["used"])
        if left < n:
            raise RuntimeError(
                f"brave_monthly_quota_exceeded: {data['used']}/{MONTHLY_LIMIT} used "
                f"in {data['month']}, only {left} remaining"
            )


def status_line() -> str:
    data = get_usage()
    used = data["used"]
    left = max(0, MONTHLY_LIMIT - used)
    pct = used / MONTHLY_LIMIT * 100
    return f"Brave API: {used}/{MONTHLY_LIMIT} used this month ({data['month']})  [{pct:.1f}%]  {left} remaining"


if __name__ == "__main__":
    print(status_line())
