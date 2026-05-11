#!/usr/bin/env python3
"""build_cex_filter.py — One-time scan to identify CEX/bridge funder addresses.

Collects Polymarket proxy wallets from the Polymarket Data API /trades endpoint
(up to 20,000 trade records → thousands of unique wallets, no auth required).
Then for each wallet fetches its USDC funding sources via Alchemy and ranks
funders by what fraction of wallets they touched.

High-frequency funders are CEXes, bridges, or Polymarket infrastructure and
should be added to _SYSTEM_ADDRESSES in sybil_clustering.py.

Usage:
    python3 build_cex_filter.py
    python3 build_cex_filter.py --max-wallets 5000 --pct-threshold 0.3
    python3 build_cex_filter.py --skip-collection   # reuse saved wallet_pool.json

Output:
    results/cex_filter/wallet_pool.json    collected wallet addresses
    results/cex_filter/funder_stats.json   full ranked funder list
    results/cex_filter/candidates.txt      above-threshold addresses + paste snippet
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
RPC_BASE   = "https://polygon-mainnet.g.alchemy.com/v2"

POLYMARKET_DATA_API = "https://data-api.polymarket.com"
USDC_POLYGON = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"

# Already hardcoded in sybil_clustering.py — excluded from candidates output
_KNOWN_SYSTEM: frozenset[str] = frozenset({
    "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",
    "0xc5d563a36ae78145c45a50134d48a1215220f80a",
    "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296",
    "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff",
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506",
    "0xe592427a0aece92de3edee1f18e0157c05861564",
    "0x401f6c983ea34274ec46f84d70b31c151321188b",
    "0x8484ef722627bf18ca5ae6bcf031c23e6e922b30",
    # Confirmed Polymarket infrastructure (40-67% of sample, added after first scan)
    "0xc288480574783bd7615170660d71753378159c47",
    "0x3a3bd7bb9528e159577f7c2e685cc81a765002e2",
    "0xf70da97812cb96acdf810712aa562db8dfa3dbef",
    "0xf7cd89be08af4d4d6b1522852ced49fc10169f64",
    "0xc536633ff12ee52e280b2af2594031060c5aaf41",
    "0xe3f18acc55091e2c48d883fc8c8413319d4ab7b0",
    "0x3a9418b2651c8164db5ebc56f12008137865e0f7",
})

_BLOCK_TIME_S = 2.3
_MIN_USDC_FUND = 10


# ---------------------------------------------------------------------------
# Polymarket Data API -- wallet collection
# ---------------------------------------------------------------------------

def _http_get(url: str) -> object:
    req = urllib.request.Request(url, headers={"User-Agent": "polymarket-cex-filter/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read())
        except Exception as e:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return {}


def collect_wallets_from_data_api(max_wallets: int) -> set[str]:
    """Collect proxy wallets from Polymarket Data API /trades.

    limit max=10,000 and offset max=10,000, giving up to 20,000 trade records.
    """
    wallets: set[str] = set()
    batch_size = 10_000

    for offset in (0, 10_000):
        if len(wallets) >= max_wallets:
            break
        url = f"{POLYMARKET_DATA_API}/trades?limit={batch_size}&offset={offset}"
        print(f"  Fetching /trades?offset={offset}…", flush=True)
        try:
            data = _http_get(url)
        except Exception as e:
            print(f"  Error at offset {offset}: {e}")
            break

        trades = data if isinstance(data, list) else data.get("data", data.get("trades", []))
        if not trades:
            print(f"  No trades at offset {offset}, stopping.")
            break

        before = len(wallets)
        for t in trades:
            w = (t.get("proxyWallet") or "").lower()
            if w and w.startswith("0x") and len(w) == 42:
                wallets.add(w)

        print(f"  offset={offset}: {len(trades)} trades, +{len(wallets) - before} new wallets ({len(wallets)} total)")
        time.sleep(0.3)

    return wallets


def collect_wallets_from_leaderboard() -> set[str]:
    """Supplement with leaderboard wallets across time periods and categories."""
    wallets: set[str] = set()
    periods    = ["ALL", "MONTH", "WEEK"]
    categories = ["OVERALL", "POLITICS", "SPORTS", "CRYPTO"]

    for period in periods:
        for category in categories:
            for offset in range(0, 1001, 50):
                url = (
                    f"{POLYMARKET_DATA_API}/v1/leaderboard"
                    f"?limit=50&offset={offset}&timePeriod={period}&category={category}&orderBy=VOL"
                )
                try:
                    data = _http_get(url)
                except Exception:
                    break
                entries = data if isinstance(data, list) else data.get("data", data.get("leaderboard", []))
                if not entries:
                    break
                for e in entries:
                    w = (e.get("proxyWallet") or "").lower()
                    if w and w.startswith("0x") and len(w) == 42:
                        wallets.add(w)
                time.sleep(0.1)

    print(f"  Leaderboard: {len(wallets)} unique wallets")
    return wallets


def load_wallets_from_file(path: str) -> set[str]:
    wallets = set()
    for line in Path(path).read_text().splitlines():
        w = line.strip().lower()
        if w.startswith("0x") and len(w) == 42:
            wallets.add(w)
    return wallets


def load_cached_wallets() -> set[str]:
    wallets: set[str] = set()
    pw_dir = SCRIPT_DIR / "results" / "polywhaler"
    if not pw_dir.exists():
        return wallets
    for date_dir in pw_dir.iterdir():
        f = date_dir / "trades.json"
        if f.exists():
            try:
                for t in json.loads(f.read_text()):
                    w = (t.get("proxyWallet") or "").lower()
                    if w:
                        wallets.add(w)
            except Exception:
                pass
    return wallets


# ---------------------------------------------------------------------------
# Alchemy -- USDC funder fetch
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    env_file = SCRIPT_DIR / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("ALCHEMY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("ALCHEMY_API_KEY", "")


def _rpc(api_key: str, method: str, params: list) -> dict:
    url = f"{RPC_BASE}/{api_key}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)
    return {}


def _latest_block(api_key: str) -> int:
    return int(_rpc(api_key, "eth_blockNumber", []).get("result", "0x0"), 16)


def get_usdc_funders(wallet: str, api_key: str, from_block: int) -> list[str]:
    totals: dict[str, float] = {}
    page_key: str | None = None
    while True:
        params: dict = {
            "toAddress":         wallet,
            "contractAddresses": [USDC_POLYGON],
            "category":          ["erc20"],
            "withMetadata":      False,
            "excludeZeroValue":  True,
            "maxCount":          "0x3e8",
            "fromBlock":         hex(from_block),
        }
        if page_key:
            params["pageKey"] = page_key
        try:
            resp = _rpc(api_key, "alchemy_getAssetTransfers", [params])
        except Exception:
            break
        result = resp.get("result", {})
        for tx in result.get("transfers", []):
            funder = (tx.get("from") or "").lower()
            value  = tx.get("value") or 0
            if funder and value:
                totals[funder] = totals.get(funder, 0.0) + float(value)
        page_key = result.get("pageKey")
        if not page_key:
            break
        time.sleep(0.05)
    return [addr for addr, amt in totals.items() if amt >= _MIN_USDC_FUND]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    out_dir = SCRIPT_DIR / "results" / "cex_filter"
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = _load_api_key()
    if not api_key:
        print("ERROR: no ALCHEMY_API_KEY in .env")
        sys.exit(1)

    # -- 1. Collect wallets --------------------------------------------------
    pool_file = out_dir / "wallet_pool.json"

    if args.skip_collection and pool_file.exists():
        wallets: set[str] = set(json.loads(pool_file.read_text()))
        print(f"Loaded {len(wallets)} wallets from saved pool.")
    else:
        wallets = set()

        cached = load_cached_wallets()
        if cached:
            print(f"Cached polywhaler wallets: {len(cached)}")
            wallets |= cached

        if args.wallets_file:
            extra = load_wallets_from_file(args.wallets_file)
            print(f"Extra wallets from file: {len(extra)}")
            wallets |= extra

        print(f"\nCollecting wallets from Polymarket Data API /trades…")
        wallets |= collect_wallets_from_data_api(args.max_wallets)

        print(f"\nCollecting wallets from Polymarket leaderboard…")
        wallets |= collect_wallets_from_leaderboard()

        wallets = {w for w in wallets if w.startswith("0x") and len(w) == 42}
        pool_file.write_text(json.dumps(sorted(wallets), indent=2))
        print(f"\nTotal unique wallets: {len(wallets)} -- saved to {pool_file}")

    if len(wallets) < 100:
        print("ERROR: fewer than 100 wallets -- sample too small.")
        sys.exit(1)

    # Cap to max_wallets for the Alchemy funder scan
    wallet_list = list(wallets)[:args.max_wallets]
    if len(wallet_list) < len(wallets):
        print(f"Capped to {args.max_wallets} wallets for funder analysis.")

    # -- 2. Fetch USDC funders -----------------------------------------------
    print(f"\nFetching latest Polygon block...")
    latest = _latest_block(api_key)
    from_block = max(0, latest - int(86_400 / _BLOCK_TIME_S * args.funding_lookback_days))
    print(f"Funding scan: last {args.funding_lookback_days}d (from block {from_block:,})")
    print(f"Querying Alchemy for {len(wallet_list)} wallets ({args.workers} workers)...\n")

    funder_wallets: dict[str, set[str]] = {}
    done = 0

    def _fetch(w: str) -> tuple[str, list[str]]:
        try:
            return w, get_usdc_funders(w, api_key, from_block)
        except Exception:
            return w, []

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_fetch, w): w for w in wallet_list}
        for future in as_completed(futures):
            wallet, funders = future.result()
            for funder in funders:
                funder_wallets.setdefault(funder, set()).add(wallet)
            done += 1
            if done % 100 == 0 or done == len(wallet_list):
                print(f"  {done}/{len(wallet_list)} wallets done", flush=True)

    # -- 3. Rank and report --------------------------------------------------
    n = len(wallet_list)
    stats = sorted(
        [
            {
                "address":           funder,
                "wallet_count":      len(touched),
                "pct_of_sample":     round(len(touched) / n * 100, 4),
                "already_hardcoded": funder in _KNOWN_SYSTEM,
            }
            for funder, touched in funder_wallets.items()
        ],
        key=lambda x: x["wallet_count"],
        reverse=True,
    )

    (out_dir / "funder_stats.json").write_text(json.dumps(stats, indent=2))
    print(f"\nFull funder stats: {len(stats)} unique funders -> results/cex_filter/funder_stats.json")

    candidates = [s for s in stats if s["pct_of_sample"] >= args.pct_threshold and not s["already_hardcoded"]]

    lines = [
        "CEX Filter Candidates",
        f"Sample: {n} wallets  |  Funding lookback: {args.funding_lookback_days}d  |  Threshold: {args.pct_threshold}%",
        "",
        f"{'Address':<44}  {'Count':>6}  {'Pct':>7}",
        "-" * 62,
    ]
    for s in candidates:
        lines.append(f"{s['address']:<44}  {s['wallet_count']:>6}  {s['pct_of_sample']:>6.2f}%")

    lines += [
        "",
        "Top 30 funders (for manual review):",
        f"{'Address':<44}  {'Count':>6}  {'Pct':>7}  {'Hardcoded':>10}",
        "-" * 72,
    ]
    for s in stats[:30]:
        hc = "yes" if s["already_hardcoded"] else ""
        lines.append(f"{s['address']:<44}  {s['wallet_count']:>6}  {s['pct_of_sample']:>6.2f}%  {hc:>10}")

    if candidates:
        lines += [
            "",
            "--- Paste snippet for sybil_clustering.py _SYSTEM_ADDRESSES ---",
            "",
        ]
        for s in candidates:
            lines.append(f'    "{s["address"]}",  # {s["pct_of_sample"]:.2f}% of {n} wallets')

    report = "\n".join(lines)
    (out_dir / "candidates.txt").write_text(report)
    print("\n" + report)
    print(f"\nCandidates file: results/cex_filter/candidates.txt")


def main() -> None:
    p = argparse.ArgumentParser(description="Build CEX address filter for sybil_clustering.py")
    p.add_argument("--max-wallets",           type=int,   default=5000, help="Max wallets to analyse (default: 5000)")
    p.add_argument("--funding-lookback-days", type=int,   default=180,  help="Days to scan for USDC funders (default: 180)")
    p.add_argument("--pct-threshold",         type=float, default=0.5,  help="Flag funders touching this %% of wallets (default: 0.5)")
    p.add_argument("--workers",               type=int,   default=3,    help="Alchemy RPC threads (default: 3, keep <=5)")
    p.add_argument("--wallets-file",          type=str,   default=None, help="Extra wallets file (one address per line)")
    p.add_argument("--skip-collection",       action="store_true",      help="Skip wallet collection, reuse saved wallet_pool.json")
    args = p.parse_args()
    run(args)


if __name__ == "__main__":
    main()
