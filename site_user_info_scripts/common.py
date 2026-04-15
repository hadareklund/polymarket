#!/usr/bin/env python3
"""Shared helpers for site user information scripts."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_TIMEOUT = 20
DEFAULT_USER_AGENT = "site-user-info-scripts/1.0"


def fetch_json(
    url: str,
    *,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    """Fetch JSON from an HTTP endpoint with basic error handling."""
    if params:
        clean_params = {k: v for k, v in params.items() if v is not None}
        if clean_params:
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}{urlencode(clean_params, doseq=True)}"

    req_headers: dict[str, str] = {
        "User-Agent": DEFAULT_USER_AGENT,
        "Accept": "application/json",
    }
    if headers:
        req_headers.update(headers)

    req = Request(url, headers=req_headers)
    try:
        with urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def unix_to_iso(value: Any) -> str | None:
    """Convert unix timestamp to UTC ISO-8601 string when possible."""
    if value is None:
        return None
    try:
        timestamp = int(value)
    except (ValueError, TypeError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def print_json(payload: Any) -> None:
    """Print JSON result in a readable format."""
    print(json.dumps(payload, indent=2, sort_keys=False))


def require_secret(cli_value: str | None, env_name: str) -> str:
    """Return secret from CLI or environment variable."""
    if cli_value:
        return cli_value
    env_value = os.getenv(env_name)
    if env_value:
        return env_value
    raise RuntimeError(
        f"Missing required secret. Provide argument or set environment variable {env_name}."
    )
