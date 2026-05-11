#!/usr/bin/env python3
"""sybil_clustering.py — Detect wallets sharing USDC funding sources on Polygon.

Uses Alchemy's alchemy_getAssetTransfers API to find USDC inflows for each
wallet, then clusters wallets with shared funders using Union-Find. Shared
funding is a classic Sybil signal — coordinated accounts often top up from
the same controlling address.

Only fires when ≥2 wallets from the *current run* share a cluster, and ignores
funders that funded more than 10 input wallets (to exclude CEXes/bridges).
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

USDC_POLYGON = "0x2791bca1f2de4661ed88a30c99a7a9449aa84174"
RPC_BASE     = "https://polygon-mainnet.g.alchemy.com/v2"

_MIN_USDC_VALUE = 100   # minimum USDC transferred to count (human-readable units)
_BLOCK_TIME_S   = 2.3   # approximate Polygon block time

# Funders that appear in this fraction of input wallets are ignored (protocol/CEX)
# E.g. 0.4 = skip any funder touching >40% of today's wallets (min 3 wallets)
_MAX_FUNDER_FRACTION = 0.4
_MAX_FUNDER_MIN      = 3   # never skip a funder that touched fewer than this many wallets

# Known Polymarket protocol contracts and major DEX/bridge addresses on Polygon.
# USDC flows through these for every trader — they're not meaningful Sybil links.
_SYSTEM_ADDRESSES: frozenset[str] = frozenset({
    "0x4bfb41d5b3570defd03c39a9a4d8de6bd8b8982e",  # Polymarket CTF Exchange
    "0xc5d563a36ae78145c45a50134d48a1215220f80a",  # Polymarket Neg Risk Exchange
    "0xd91e80cf2e7be2e162c6513ced06f1dd0da35296",  # Polymarket USDC vault
    "0x4d97dcd97ec945f40cf65f87097ace5ea0476045",  # Polymarket deposit/relayer
    "0x2791bca1f2de4661ed88a30c99a7a9449aa84174",  # USDC contract itself
    "0xa5e0829caced8ffdd4de3c43696c57f7d7a678ff",  # QuickSwap router
    "0x1b02da8cb0d097eb8d57a175b88c7d8b47997506",  # SushiSwap router
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3 router
    "0x401f6c983ea34274ec46f84d70b31c151321188b",  # Polygon PoS bridge
    "0x8484ef722627bf18ca5ae6bcf031c23e6e922b30",  # Polygon plasma bridge
    # Confirmed Polymarket infrastructure — found in 39–77% of 5000-wallet sample
    "0xc288480574783bd7615170660d71753378159c47",  # Polymarket infrastructure (32%)
    "0x3a3bd7bb9528e159577f7c2e685cc81a765002e2",  # Polymarket infrastructure (44%)
    "0xf70da97812cb96acdf810712aa562db8dfa3dbef",  # Polymarket relayer/EOA (59%)
    "0xf7cd89be08af4d4d6b1522852ced49fc10169f64",  # Polymarket infrastructure (18%)
    "0xc536633ff12ee52e280b2af2594031060c5aaf41",  # Polymarket infrastructure (11%)
    "0xe3f18acc55091e2c48d883fc8c8413319d4ab7b0",  # Polymarket infrastructure (43%)
    "0x3a9418b2651c8164db5ebc56f12008137865e0f7",  # Polymarket infrastructure (45%)
    # High-frequency funders — confirmed infrastructure/CEX (3–21% of 5000 wallets)
    "0x05cd9922a5d37fae921fc5dee280a9dbc4c3b393",  # 20.78% of 5000 wallets
    "0xb768891e3130f6df18214ac804d4db76c2c37730",  # 12.16% of 5000 wallets
    "0xf5042e6ffac5a625d4e7848e0b01373d8eb9e222",  # 11.30% of 5000 wallets
    "0xabb2acd3be814a80e502575d6c1dc5f789e9cd10",  # 7.12% of 5000 wallets
    "0x56c262027e0de4aea31d2489529cb25d23e58a8b",  # 6.84% of 5000 wallets
    "0xa67d7eb4dc68fa6ce8e34ef8cadaf075b9893fbb",  # 6.40% of 5000 wallets
    "0xd36ec33c8bed5a9f7b6630855f1533455b98a418",  # 4.78% of 5000 wallets
    "0xb92fe925dc43a0ecde6c8b1a2709c170ec4fff4f",  # 4.32% of 5000 wallets
    "0xd15fe25ed0dba12fe05e7029c88b10c25e8880e3",  # 3.62% of 5000 wallets
    "0x1510565e93c9729410b6e41088e014e312fd8829",  # 3.50% of 5000 wallets
    # Mid-frequency funders — likely smaller CEX/on-ramp (1–2% of 5000 wallets)
    "0xc417fd8e9661c0d2120b64a04bb3278c17e99db1",  # 1.38% of 5000 wallets
    "0x2924f3eb2f26d47ecb0283c645d596100ef3001f",  # 1.04% of 5000 wallets
    # Lower-frequency funders — probable CEX/on-ramp (0.5–1% of 5000 wallets)
    "0x4be70a9b53e89b202bd794086f413894c5082709",  # 0.90% of 5000 wallets
    "0x19f1a546bdc076009d75e7c0dfb49be7bb51ce8f",  # 0.88% of 5000 wallets
    "0x2bb27b73c602643f42471d4751fe4fc4eebefbd1",  # 0.84% of 5000 wallets
    "0xada5bb90d0de0bd1b6f3938708f49295a8d1f7cb",  # 0.82% of 5000 wallets
    "0x331d9a049d496385998067abf6cbb6371c8d2466",  # 0.76% of 5000 wallets
    "0x370a7e2d300c14d79d4a7ee07aaca46c4b3012cf",  # 0.76% of 5000 wallets
    "0xca7ded7e4f4ba8ab3b10009236ae6d1b95094589",  # 0.70% of 5000 wallets
    "0xd152f549545093347a162dce210e7293f1452150",  # 0.68% of 5000 wallets
    "0x18dd3c14e34c1bc379f7538068c59160d9f68e25",  # 0.64% of 5000 wallets
    "0xa5a5491bca93dd4c076e4906e79e7673f4a5a142",  # 0.52% of 5000 wallets
})


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _load_api_key() -> str:
    env_file = Path(__file__).resolve().parent / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("ALCHEMY_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.getenv("ALCHEMY_API_KEY", "")


def _rpc(api_key: str, method: str, params: list) -> dict:
    url = f"{RPC_BASE}/{api_key}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return {}


def _latest_block(api_key: str) -> int:
    resp = _rpc(api_key, "eth_blockNumber", [])
    return int(resp.get("result", "0x0"), 16)


# ---------------------------------------------------------------------------
# USDC funder fetch via alchemy_getAssetTransfers
# ---------------------------------------------------------------------------

def get_usdc_funders(
    wallet: str,
    api_key: str,
    from_block: int,
) -> list[str]:
    """Return addresses that sent ≥$100 USDC to *wallet* since *from_block*.

    Paginates through all results using Alchemy's pageKey cursor.
    """
    totals: dict[str, float] = {}  # funder_address → cumulative USDC
    page_key: str | None = None

    while True:
        params: dict = {
            "toAddress":         wallet.lower(),
            "contractAddresses": [USDC_POLYGON],
            "category":          ["erc20"],
            "withMetadata":      False,
            "excludeZeroValue":  True,
            "maxCount":          "0x3e8",  # 1000 per page
            "fromBlock":         hex(from_block),
        }
        if page_key:
            params["pageKey"] = page_key

        try:
            resp = _rpc(api_key, "alchemy_getAssetTransfers", [params])
        except Exception as e:
            print(f"    Sybil RPC error ({wallet[:10]}…): {e}")
            break

        if "error" in resp:
            print(f"    Sybil API error ({wallet[:10]}…): {resp['error']}")
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
        time.sleep(0.1)

    return [addr for addr, amt in totals.items() if amt >= _MIN_USDC_VALUE]


# ---------------------------------------------------------------------------
# Union-Find
# ---------------------------------------------------------------------------

class _UF:
    def __init__(self) -> None:
        self._p: dict[str, str] = {}
        self._r: dict[str, int] = {}

    def find(self, x: str) -> str:
        if x not in self._p:
            self._p[x] = x
            self._r[x] = 0
        if self._p[x] != x:
            self._p[x] = self.find(self._p[x])
        return self._p[x]

    def union(self, x: str, y: str) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._r.get(rx, 0) < self._r.get(ry, 0):
            rx, ry = ry, rx
        self._p[ry] = rx
        if self._r.get(rx, 0) == self._r.get(ry, 0):
            self._r[rx] = self._r.get(rx, 0) + 1


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_clusters(
    wallets: list[str],
    api_key: str | None = None,
    lookback_days: int = 90,
    max_workers: int = 3,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Cluster wallets that share a common USDC funder on Polygon.

    Args:
        wallets: Wallet addresses to analyse.
        api_key: Alchemy API key. Reads from .env if omitted.
        lookback_days: How far back to scan (default 90 days).
        max_workers: Concurrent RPC threads (keep ≤3 to respect rate limits).

    Returns:
        Tuple of:
          - {root_wallet: [member_wallets]} for every cluster with ≥2 members.
          - {root_wallet: [funder_addresses]} listing the shared funders that
            linked the cluster (excludes system/CEX addresses).
    """
    if not wallets:
        return {}

    key = api_key or _load_api_key()
    if not key:
        print("  Sybil: no ALCHEMY_API_KEY — skipping cluster analysis.")
        return {}

    wallets = [w.lower() for w in wallets]

    print(f"  Sybil: fetching latest Polygon block…")
    try:
        latest = _latest_block(key)
    except Exception as e:
        print(f"  Sybil: RPC unavailable ({e}) — skipping.")
        return {}

    from_block = max(0, latest - int(86_400 / _BLOCK_TIME_S * lookback_days))
    print(f"  Sybil: scanning last {lookback_days}d (from block {from_block:,}) for {len(wallets)} wallets…")

    wallet_funders: dict[str, list[str]] = {}

    def _fetch(w: str) -> tuple[str, list[str]]:
        try:
            return w, get_usdc_funders(w, key, from_block)
        except Exception as e:
            print(f"  Sybil: fetch error for {w[:10]}…: {e}")
            return w, []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for wallet, funders in pool.map(_fetch, wallets):
            wallet_funders[wallet] = funders

    # How many input wallets did each funder touch?
    funder_degree: dict[str, int] = {}
    for funders in wallet_funders.values():
        for f in funders:
            funder_degree[f] = funder_degree.get(f, 0) + 1

    n_wallets = len(wallets)
    max_degree = max(_MAX_FUNDER_MIN, int(n_wallets * _MAX_FUNDER_FRACTION))

    def _is_system(funder: str) -> bool:
        return funder in _SYSTEM_ADDRESSES or funder_degree.get(funder, 0) > max_degree

    # Build funder → wallets map (excluding system/high-degree addresses)
    funder_to_wallets: dict[str, list[str]] = {}
    for wallet, funders in wallet_funders.items():
        for funder in funders:
            if _is_system(funder):
                continue
            funder_to_wallets.setdefault(funder, []).append(wallet)

    # Union wallets that share a meaningful funder
    uf = _UF()
    for linked in funder_to_wallets.values():
        if len(linked) < 2:
            continue
        for i in range(1, len(linked)):
            uf.union(linked[0], linked[i])

    # Collect clusters with ≥2 members
    groups: dict[str, list[str]] = {}
    for wallet in wallets:
        root = uf.find(wallet)
        groups.setdefault(root, []).append(wallet)

    clusters = {root: members for root, members in groups.items() if len(members) >= 2}

    # Map each cluster root to the funder addresses that link its members
    cluster_funders: dict[str, list[str]] = {}
    for funder, linked in funder_to_wallets.items():
        if len(linked) < 2:
            continue
        roots_touched: set[str] = set()
        for w in linked:
            root = uf.find(w)
            if root in clusters:
                roots_touched.add(root)
        for root in roots_touched:
            cluster_funders.setdefault(root, []).append(funder)

    if clusters:
        total = sum(len(m) for m in clusters.values())
        print(f"  Sybil: found {len(clusters)} cluster(s) covering {total} wallets")
    else:
        print("  Sybil: no shared-funder clusters detected")

    return clusters, cluster_funders
