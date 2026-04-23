#!/usr/bin/env python3
"""
Fetch full on-chain holder wallets for a Polymarket market and resolve usernames.

Uses only public endpoints:
- Gamma API: event and market discovery
- Alchemy NFT API (Polygon): full ERC-1155 token owners per outcome token
- Data API: off-chain username resolution per wallet via user activity
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import Request, urlopen

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_BASE = "https://data-api.polymarket.com"
ALCHEMY_POLYGON_BASE = "https://polygon-mainnet.g.alchemy.com"
POLY_CONDITIONAL_TOKENS_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
DEFAULT_EVENT_URL = "https://polymarket.com/event/fda-approves-retatrutide-this-year"
USER_AGENT = "Mozilla/5.0 (compatible; polymarket-holder-usernames/1.0)"


def safe_slug_for_filename(slug: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in slug)


def log_status(message: str) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}", file=sys.stderr, flush=True)


def write_output_file(
    path: str,
    yes_usernames: List[str],
    no_usernames: List[str],
) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        for username in yes_usernames:
            handle.write(f"{username}\n")

        handle.write("\n")

        for username in no_usernames:
            handle.write(f"{username}\n")


def http_get_json(url: str, timeout: int = 30) -> Any:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="ignore")
        except Exception:
            pass
        raise RuntimeError(f"HTTP {exc.code} for {url}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Network error for {url}: {exc}") from exc


def extract_slug(event_url_or_slug: str) -> str:
    parsed = urlparse(event_url_or_slug)
    if parsed.scheme and parsed.netloc:
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) >= 2 and parts[0] == "event":
            return parts[1]
        if parts:
            return parts[-1]
        raise ValueError(f"Could not extract slug from URL: {event_url_or_slug}")

    # Accept a raw slug too.
    return event_url_or_slug.strip("/")


def fetch_event_by_slug(slug: str) -> Dict[str, Any]:
    # Path endpoint is direct and usually returns one event object.
    url = f"{GAMMA_BASE}/events/slug/{quote(slug)}"
    data = http_get_json(url)

    if isinstance(data, dict):
        return data

    if isinstance(data, list) and data:
        return data[0]

    # Fallback to query endpoint.
    fallback = http_get_json(f"{GAMMA_BASE}/events?{urlencode({'slug': slug})}")
    if isinstance(fallback, list) and fallback:
        return fallback[0]

    raise RuntimeError(f"No event found for slug: {slug}")


def parse_json_array_field(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            return []
    return []


def extract_binary_markets(
    event: Dict[str, Any],
) -> List[Tuple[Dict[str, Any], str, str]]:
    """Return list of (market, yes_token_id, no_token_id) for every binary Yes/No market."""
    markets = event.get("markets", [])
    if not markets:
        raise RuntimeError("No markets found in event payload.")

    result = []
    for market in markets:
        outcomes = parse_json_array_field(market.get("outcomes"))
        token_ids = parse_json_array_field(market.get("clobTokenIds"))
        if len(outcomes) != len(token_ids):
            continue
        mapping: Dict[str, str] = {
            o.strip(): tid.strip()
            for o, tid in zip(outcomes, token_ids)
            if isinstance(o, str) and isinstance(tid, str)
        }
        if "Yes" in mapping and "No" in mapping:
            result.append((market, mapping["Yes"], mapping["No"]))

    if not result:
        raise RuntimeError("No binary Yes/No markets found in this event.")

    return result


def fetch_owners_for_token_via_alchemy(
    token_id_decimal: str,
    api_key: str,
    include_zero_address: bool,
    outcome_label: str,
    contract_address: str = POLY_CONDITIONAL_TOKENS_CONTRACT,
) -> List[str]:
    token_id_hex = hex(int(token_id_decimal))
    owners: Set[str] = set()
    page_key: Optional[str] = None
    page_num = 0

    log_status(
        f"Fetching {outcome_label} owners from Alchemy for token {token_id_decimal[:14]}..."
    )

    while True:
        page_num += 1
        params = {
            "contractAddress": contract_address,
            "tokenId": token_id_hex,
            "withTokenBalances": "true",
        }
        if page_key:
            params["pageKey"] = page_key

        url = f"{ALCHEMY_POLYGON_BASE}/nft/v3/{quote(api_key)}/getOwnersForNFT?{urlencode(params)}"
        payload = http_get_json(url, timeout=45)

        before = len(owners)
        for owner_entry in payload.get("owners", []):
            if isinstance(owner_entry, str):
                wallet = owner_entry.lower()
            elif isinstance(owner_entry, dict):
                wallet = str(owner_entry.get("ownerAddress", "")).lower()
            else:
                wallet = ""

            if wallet.startswith("0x") and len(wallet) == 42:
                owners.add(wallet)

        added = len(owners) - before
        log_status(
            f"{outcome_label} owners page {page_num}: +{added} (total {len(owners)})"
        )

        page_key = payload.get("pageKey")
        if not page_key:
            break

    if not include_zero_address:
        owners.discard(ZERO_ADDRESS)

    log_status(f"Completed {outcome_label} owner fetch: {len(owners)} wallets")
    return sorted(owners)


def resolve_wallet_username(wallet: str) -> str:
    # Public Data API activity includes profile metadata fields like name/pseudonym.
    url = f"{DATA_BASE}/activity?{urlencode({'user': wallet, 'limit': 1})}"

    try:
        payload = http_get_json(url, timeout=20)
    except Exception:
        return ""

    if not isinstance(payload, list) or not payload:
        return ""

    first = payload[0]
    if not isinstance(first, dict):
        return ""

    name = str(first.get("name") or "").strip()
    pseudonym = str(first.get("pseudonym") or "").strip()
    return name or pseudonym


def resolve_usernames_for_wallets(
    wallets: Sequence[str],
    workers: int,
) -> Dict[str, str]:
    resolved: Dict[str, str] = {}
    total = len(wallets)
    completed = 0

    log_status(f"Resolving usernames for {total} wallets using {workers} workers...")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(resolve_wallet_username, wallet): wallet for wallet in wallets
        }
        for future in as_completed(futures):
            wallet = futures[future]
            try:
                resolved[wallet] = future.result().strip()
            except Exception:
                resolved[wallet] = ""

            completed += 1
            if completed % 10 == 0 or completed == total:
                found = sum(1 for value in resolved.values() if value)
                log_status(
                    f"Username resolution progress: {completed}/{total} complete, {found} resolved"
                )

    return resolved


def build_usernames(
    wallets: Sequence[str],
    usernames: Dict[str, str],
    wallet_fallback: bool,
) -> List[str]:
    rows: List[str] = []
    for wallet in wallets:
        username = (usernames.get(wallet) or "").strip()
        if not username and wallet_fallback:
            username = wallet
        if username and not username.lower().startswith("0x"):
            rows.append(username)
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Two-step pipeline: (1) get all on-chain holder wallets per outcome token, "
            "(2) resolve wallets to usernames using Polymarket public off-chain metadata."
        )
    )
    parser.add_argument(
        "event",
        nargs="?",
        default=DEFAULT_EVENT_URL,
        help="Event URL or slug (default: FDA approves Retatrutide this year event)",
    )
    parser.add_argument(
        "--alchemy-api-key",
        default=os.getenv("ALCHEMY_API_KEY", "demo"),
        help="Alchemy API key for Polygon NFT owner queries (default: env ALCHEMY_API_KEY or 'demo').",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=12,
        help="Concurrent worker count for wallet-to-username resolution (default: 12).",
    )
    parser.add_argument(
        "--wallet-fallback",
        action="store_true",
        help="If username cannot be resolved, write the wallet address in the username column.",
    )
    parser.add_argument(
        "--exclude-zero-address",
        action="store_true",
        help="Exclude 0x000...0000 from owner sets.",
    )
    parser.add_argument(
        "--output",
        help="Output txt path (default: <event-slug>_full_holder_usernames.txt)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.workers <= 0:
        print("--workers must be > 0", file=sys.stderr)
        return 2

    try:
        slug = extract_slug(args.event)
        log_status(f"Resolved event slug: {slug}")

        log_status("Fetching event metadata from Gamma API...")
        event = fetch_event_by_slug(slug)
        binary_markets = extract_binary_markets(event)
        log_status(f"Found {len(binary_markets)} binary Yes/No market(s)")

        # Step 1: On-chain owner extraction for every market.
        all_yes_wallets: Set[str] = set()
        all_no_wallets: Set[str] = set()
        # wallet → {market_slug: {question, yes, no}}
        wallet_market_positions: Dict[str, Dict[str, Any]] = {}

        for market, yes_token, no_token in binary_markets:
            market_slug = market.get("slug") or market.get("conditionId", "unknown")
            question = market.get("question", market_slug)

            yes_set = set(fetch_owners_for_token_via_alchemy(
                token_id_decimal=yes_token,
                api_key=args.alchemy_api_key,
                include_zero_address=not args.exclude_zero_address,
                outcome_label=f"Yes ({market_slug})",
            ))
            no_set = set(fetch_owners_for_token_via_alchemy(
                token_id_decimal=no_token,
                api_key=args.alchemy_api_key,
                include_zero_address=not args.exclude_zero_address,
                outcome_label=f"No ({market_slug})",
            ))

            all_yes_wallets |= yes_set
            all_no_wallets |= no_set

            for wallet in yes_set | no_set:
                wallet_market_positions.setdefault(wallet, {})[market_slug] = {
                    "question": question,
                    "yes": wallet in yes_set,
                    "no": wallet in no_set,
                }

        all_wallets = sorted(all_yes_wallets | all_no_wallets)
        log_status(f"Combined owner universe: {len(all_wallets)} unique wallets across all markets")

        # Step 2: Off-chain username resolution.
        wallet_to_username = resolve_usernames_for_wallets(
            wallets=all_wallets,
            workers=args.workers,
        )

        yes_usernames = build_usernames(
            sorted(all_yes_wallets), wallet_to_username, args.wallet_fallback
        )
        no_usernames = build_usernames(
            sorted(all_no_wallets), wallet_to_username, args.wallet_fallback
        )

        results_dir = Path(__file__).resolve().parent / "results"
        results_dir.mkdir(exist_ok=True)
        output_path = (
            args.output
            or str(results_dir / f"{safe_slug_for_filename(slug)}_full_holder_usernames.txt")
        )
        write_output_file(
            path=output_path,
            yes_usernames=yes_usernames,
            no_usernames=no_usernames,
        )

        # Write per-market positions sidecar (username-keyed).
        username_market_positions: Dict[str, Any] = {}
        for wallet, markets_pos in wallet_market_positions.items():
            username = (wallet_to_username.get(wallet) or "").strip()
            if not username or username.lower().startswith("0x"):
                continue
            for market_slug, pos in markets_pos.items():
                username_market_positions.setdefault(username, {})[market_slug] = pos

        sidecar_path = str(results_dir / f"{safe_slug_for_filename(slug)}_market_positions.json")
        with open(sidecar_path, "w", encoding="utf-8") as f:
            json.dump(username_market_positions, f, indent=2, ensure_ascii=False)

        print(f"Markets processed: {len(binary_markets)}", file=sys.stderr)
        print(f"Yes holders (union, on-chain): {len(all_yes_wallets)}", file=sys.stderr)
        print(f"No holders (union, on-chain): {len(all_no_wallets)}", file=sys.stderr)
        print(f"Union wallets: {len(all_wallets)}", file=sys.stderr)
        print(f"Yes usernames written: {len(yes_usernames)}", file=sys.stderr)
        print(f"No usernames written: {len(no_usernames)}", file=sys.stderr)
        resolved_unique = len(
            {name for name in wallet_to_username.values() if name.strip()}
        )
        print(f"Resolved unique usernames: {resolved_unique}", file=sys.stderr)
        unresolved = sum(
            1 for wallet in all_wallets
            if not wallet_to_username.get(wallet, "").strip()
        )
        print(f"Unresolved wallet usernames: {unresolved}", file=sys.stderr)
        print(f"Wrote dataset to: {output_path}", file=sys.stderr)
        print(f"Wrote market positions to: {sidecar_path}", file=sys.stderr)
        return 0

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
