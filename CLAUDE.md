# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

This project is a **copy-trading intelligence system for Polymarket**. The goal is to identify traders who appear to have material non-public information, so the operator can decide whether to mirror their positions.

The system does **not** place trades automatically. It acts as a research assistant: it gathers evidence, scores each trader, and delivers a concise Telegram report summarising the key facts. The operator reads the report and makes the final call on whether to copy the trade.

The pipeline finds candidates by combining:
- **On-chain signals** — trade size, timing, Polywhaler insider score, Falcon analytics (PnL, win rate, Sharpe)
- **OSINT** — social profiles (GitHub, LinkedIn, HuggingFace, etc.) cross-referenced against the market subject to detect professional overlap
- **LLM analysis** — Claude condenses the scored data into a plain-English brief highlighting the strongest cases

## Primary pipeline: daily Telegram intelligence report

```
polywhaler.com trade feed
  → polywhaler_monitor.py          fetch high-insiderScore trades, OSINT new wallets
      → run.py --usernames-file    site scrapers + Falcon on-chain enrichment per trader
      → score_against_market()     points: entity match, finance employer, Falcon metrics
      → analysis.json + report.txt ranked trader list
  → auto_monitor.py               drive the full daily run
      → polywhaler_monitor.py      (step 1 above)
      → claude -p                  LLM converts ranked JSON to intelligence brief
      → Telegram sendMessage       post brief to channel
```

Run the full pipeline:
```bash
python3 auto_monitor.py                          # standard daily run
python3 auto_monitor.py --threshold 15 --pages 6 # lower bar, more trades
python3 auto_monitor.py --no-osint               # score cached profiles, skip scraping
python3 auto_monitor.py --no-telegram            # run + analyse, skip posting
python3 auto_monitor.py --dry-run                # analyse today's cached data only
```

Scheduled via cron (runs daily at 08:30 UTC):
```
30 8 * * * cd /home/kali/polymarket && /usr/bin/python3 auto_monitor.py >> /home/kali/polymarket/results/auto_monitor.log 2>&1
```

## Secondary pipeline: event-holder deep-dive

For targeted analysis of who holds positions in a specific market:

```
Polymarket event URL
  → run.py
      → get_event_holder_usernames.py
          → Gamma API            event/market metadata
          → Alchemy NFT API      on-chain ERC-1155 owners per outcome token
          → Polymarket Data API  wallet → username resolution (concurrent)
          → results/<slug>_full_holder_usernames.txt
          → results/<slug>_wallet_map.json          (username → wallet, for Falcon)
          → results/<slug>_market_positions.json    (per-market yes/no/shares/USD)
      → Sherlock                 social-network probes for each username
      → site_user_info_scripts/working/<site>_user_info.py per claimed site
      → Falcon API               on-chain analytics per wallet (agent 586 + 581)
      → results/<slug>/<username>.json  per-user profile
  → analyze_insider_trading.py  score profiles against company/finance keywords
```

Run the event pipeline:
```bash
python3 run.py "https://polymarket.com/event/<slug>"
python3 run.py "https://polymarket.com/event/<slug>" --alchemy-api-key <key> --workers 10
python3 run.py --usernames-file results/some_usernames.txt   # skip holder fetch
python3 run.py --markets-file markets.txt                    # batch mode
python3 run.py "https://polymarket.com/event/<slug>" --with-sherlock  # enable Sherlock
python3 analyze_insider_trading.py <slug>                    # score collected profiles
```

## Setup

```bash
# Initialize Sherlock submodule
git submodule update --init --recursive

# Install Sherlock and all dependencies
python3 -m pip install -e ./sherlock
```

Set API keys in `.env` at the project root:

```
ALCHEMY_API_KEY=...          # Polygon NFT owner queries (get_event_holder_usernames.py)
FALCON_API_TOKEN=...         # Falcon/polymarketanalytics on-chain data (falcon_analytics.py)
TELEGRAM_BOT_TOKEN=...       # Telegram bot (auto_monitor.py)
TELEGRAM_CHAT_ID=...         # Target channel/chat ID
TELEGRAM_TOPIC_ID=...        # Optional: forum-channel topic ID
BRAVE_API_KEY=...            # LinkedIn SERP lookup (linkedin_batch.py)
REDDIT_ACCESS_TOKEN=...      # Reddit scraper (site_user_info_scripts/api_auth/)
```

## Scoring system

### polywhaler_monitor.py — `score_against_market()`

Points added per flag (higher = more suspicious):

| Flag type | Points | Description |
|-----------|--------|-------------|
| `direct_entity_match` (LinkedIn) | 20 | Employer matches market subject via LinkedIn |
| `direct_entity_match` | 18 | Employer matches via GitHub/HuggingFace |
| `category_*_keyword` | 8 | Domain keyword in professional profile |
| `investment_bank` | 8 | Works at known investment bank |
| `vc_firm` / `securities_law` | 6 | VC or securities law firm |
| `investment_firm_company` | 5 | Generic investment firm in company field |
| `polywhaler_insider_score` | 0–10 | Polywhaler's raw score ÷ 6, capped at 10 |
| `large_trade` (≥$100k) | 3 | Large single trade |
| `medium_trade` (≥$25k) | 1 | Medium trade |
| `no_online_presence` | 2 | Ghost account with insider score |
| `falcon_large_pnl` (≥$50k lifetime) | 2 | Large historical profit |
| `falcon_high_roi` (≥15% with ≥50 trades) | 2 | Consistently profitable trader |
| `falcon_high_win_rate` (≥75%) | 2 | Suspiciously accurate recent bets |
| `falcon_high_sharpe` (≥2.0) | 2 | Risk-adjusted returns suggest info advantage |
| `falcon_concentrated_bets` (<0.3 diversity) | 1 | Bets concentrated in one category |

### analyze_insider_trading.py — for event holder analysis

Separate scorer for the event-holder pipeline. Reads `results/<slug>/<username>.json` files and scores against company keywords, corporate emails, finance infrastructure, bet concentration.

## Falcon API (`falcon_analytics.py`)

Wraps `https://narrative.agent.heisenberg.so/api/v2/semantic/retrieve/parameterized`.

**Request format** — must use `agent_id` (not `retriever_id`) and `params` (not `parameters`):
```json
{"agent_id": 586, "params": {"wallet_address": "0x..."}, "formatter_config": {"format_type": "raw"}}
```

**Agents used:**
- `586` Lifetime Performance: `params: {wallet_address}` → total_pnl, roi_pct, total_trades, avg_trade_size
- `581` Wallet 360: `params: {proxy_wallet, window_days}` → 60+ risk/behavior metrics; tries 30d then falls back to 7d
- `579` Top Traders leaderboard: `params: {wallet_address, leaderboard_period}` → rank, pnl, roi

**Result stored in profile JSON** under `polymarket_analytics`:
```json
{
  "polymarket_analytics": {
    "wallet": "0x...",
    "lifetime_performance": {"total_pnl": "...", "roi_pct": "...", ...},
    "wallet_360_30d": {"win_rate": 0.72, "sharpe_ratio": 1.4, ...}
  }
}
```

## Key files

| File | Role |
|------|------|
| `auto_monitor.py` | **Entry point** for the daily pipeline: runs monitor → Claude → Telegram |
| `polywhaler_monitor.py` | Fetches polywhaler trade feed, runs OSINT, scores traders, writes analysis.json |
| `falcon_analytics.py` | Falcon API client: `enrich_wallet()`, `lifetime_performance()`, `wallet_360()` |
| `run.py` | Event-holder pipeline: holders → Sherlock → site scrapers → Falcon enrichment |
| `get_event_holder_usernames.py` | Alchemy + Polymarket Data API, writes usernames txt + wallet map + positions JSON |
| `analyze_insider_trading.py` | Post-hoc scorer for event-holder profiles; IPO/company keyword matching |
| `linkedin_batch.py` | Batch LinkedIn SERP lookup; updates profile JSONs in-place |
| `site_user_info_scripts/working/` | Per-site scrapers returning JSON to stdout; all confirmed working |
| `site_user_info_scripts/not_working/` | Pending implementation; do NOT call from other scripts |

## Data flow detail: polywhaler daily run

```
auto_monitor.py
  ↓ subprocess
polywhaler_monitor.py
  ↓ fetch trades from polywhaler.com/api/trades
  filter insiderScore ≥ threshold
  dedup against state.json (seen wallets)
  ↓ new wallets only
  write new_usernames.txt + new_usernames_wallet_map.json → out_dir/
  ↓ subprocess
  run.py --usernames-file new_usernames.txt
    → site scrapers (GitHub, HuggingFace, LinkedIn, etc.)
    → Falcon API (agent 586 + 581 per wallet from wallet_map)
    → results/new_usernames/<username>.json  ← includes polymarket_analytics
  ↓ optional subprocess
  linkedin_batch.py → updates profile JSONs with LinkedIn snippets
  ↓ load profiles
  score_against_market() per trader
    OSINT signals: entity match, employer keywords, finance infrastructure
    Falcon signals: pnl, roi, win_rate, sharpe, concentration
  → out_dir/analysis.json   (scored, sorted)
  → out_dir/report.txt      (human-readable)
  ↓ back in auto_monitor.py
  build_prompt() → compact JSON of top traders + flags + on_chain metrics
  ↓ subprocess
  claude -p "<system prompt + data>"
    → 1–10 line intelligence brief
  → out_dir/claude_analysis.txt
  ↓ Telegram Bot API
  sendMessage to TELEGRAM_CHAT_ID
```

## Output structure

```
results/
  polywhaler/
    state.json                        seen wallets (prevents re-processing)
    YYYY-MM-DD/
      trades.json                     raw flagged trades
      analysis.json                   scored traders (sorted by our_score desc)
      report.txt                      human-readable ranked summary
      claude_analysis.txt             LLM intelligence brief
      linkedin_queries.json           queries submitted to linkedin_batch.py
  new_usernames/                      profiles from polywhaler run
    <username>.json
    summary.json
    checkpoint.json
  <event-slug>/                       profiles from event-holder run
    <username>.json                   includes polymarket_analytics if wallet found
    summary.json
    linkedin_queries.json
  <slug>_full_holder_usernames.txt    Yes holders / blank / No holders
  <slug>_wallet_map.json              {username: wallet_address}
  <slug>_market_positions.json        {username: {market_slug: {yes, no, shares, usd}}}
```

## Sherlock submodule

`sherlock/` is the upstream `sherlock-project/sherlock` repo. Do not edit files under it. If a site probe needs fixing, adjust `TARGET_SITES` / `TARGET_SITE_ALIASES` in `search_usernames_targeted_sherlock.py` instead.

## Adding a new site scraper

1. Create `site_user_info_scripts/working/<site>_user_info.py` — takes `username` as argv[1], prints JSON to stdout, exits 0 on success.
2. Add to `SHERLOCK_TO_SCRIPT` in `run.py` (maps Sherlock site name → script stem).
3. If not in Sherlock, add stem to `ALWAYS_RUN_SCRIPTS` in `run.py`.
4. Test: `python3 site_user_info_scripts/working/<site>_user_info.py <testuser>`
