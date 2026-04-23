# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This project is a collection of Python utility scripts for OSINT on Polymarket prediction market participants. The two main workflows are:

1. **Holder extraction**: Fetch on-chain ERC-1155 token holders for a Polymarket event from the Alchemy NFT API (Polygon), then resolve wallet addresses to usernames via the Polymarket Data API.
2. **Username search**: Run a targeted subset of Sherlock social network probes against a known username list.

The `sherlock/` directory is a **git submodule** pointing to the upstream Sherlock project. It must be initialized before `search_usernames_targeted_sherlock.py` will work.

## Setup

```bash
# Initialize Sherlock submodule
git submodule update --init --recursive

# Install Sherlock and all dependencies into local venv
python3 -m pip install -e ./sherlock
```

The venv is at `.venv/`. Scripts expect it at that path; `general_sherlock/run.py` auto-detects it.

Set API keys via env vars or a `.env` file at the project root:

```
ALCHEMY_API_KEY=...
REDDIT_ACCESS_TOKEN=...
STACKEXCHANGE_API_KEY=...
TWITTER_BEARER_TOKEN=...
```

## Commands

```bash
# Full end-to-end OSINT pipeline (holder fetch → Sherlock → per-site info → per-user JSON)
python3 run.py "https://polymarket.com/event/<slug>"
python3 run.py "https://polymarket.com/event/<slug>" --alchemy-api-key <key> --workers 10 --timeout 20
python3 run.py --usernames-file results/some_usernames.txt   # skip holder fetch
python3 run.py "https://polymarket.com/event/<slug>" --skip-sherlock  # run all scripts, skip Sherlock
python3 run.py --markets-file markets.txt  # batch: one event URL per line, processed sequentially
# Output: results/<slug>/<username>.json per user, containing username, position, sherlock_claimed, profiles
# markets.txt format: one Polymarket event URL (or slug) per line; blank lines and # comments ignored

# Fetch holders + resolve usernames for a Polymarket event
python3 get_event_holder_usernames.py "https://polymarket.com/event/<slug>"
python3 get_event_holder_usernames.py "https://polymarket.com/event/<slug>" --alchemy-api-key <key> --workers 20

# Targeted Sherlock search (against a fixed curated site list)
python3 search_usernames_targeted_sherlock.py username1 username2
python3 search_usernames_targeted_sherlock.py --usernames-file results/some_usernames.txt

# General Sherlock runner (all sites, batch)
python3 general_sherlock/run.py usernames.txt --timeout 10

# Site-specific profile lookup (public API)
python3 site_user_info_scripts/working/github_user_info.py octocat
python3 site_user_info_scripts/working/hackernews_user_info.py pg

# Auth-gated lookups
REDDIT_ACCESS_TOKEN="..." python3 site_user_info_scripts/api_auth/reddit_user_info.py spez

# Aggregate all collectors into one structured record per user
python3 site_user_info_scripts/aggregate_user_info_to_txt.py <username>

# Run Sherlock's own tests (from sherlock/ subdir)
cd sherlock && python3 -m pytest
# Skip online/validate_targets tests (default via pytest.ini)
cd sherlock && python3 -m pytest -m "not online and not validate_targets"
# Run a single test file
cd sherlock && python3 -m pytest tests/test_probes.py
```

## Architecture

### Data flow

```
Polymarket event URL
  → run.py  (full pipeline)
      → get_event_holder_usernames.py
          → Gamma API (event/market metadata)
          → Alchemy NFT API (on-chain ERC-1155 owners per outcome token)
          → Polymarket Data API (wallet → username resolution, concurrent)
          → results/<slug>_full_holder_usernames.txt  (Yes holders, blank line, No holders)
      → Sherlock (sherlock_project.sherlock) against sites with working scripts
      → site_user_info_scripts/working/<site>_user_info.py per claimed site
      → results/<slug>/<username>.json  (per-user profile with position info)

  (standalone) get_event_holder_usernames.py
      → results/<slug>_full_holder_usernames.txt
          → search_usernames_targeted_sherlock.py
              → sherlock submodule (sherlock_project.sherlock)
              → results/targeted_sherlock_results.json
```

### Key files

- **`run.py`** — end-to-end pipeline: fetches holders, runs Sherlock, calls per-site info scripts, writes `results/<slug>/<username>.json` per user. Each JSON includes `position: {"yes": bool, "no": bool}` derived from the holder output file's Yes/No sections.
- **`get_event_holder_usernames.py`** — self-contained, no third-party deps (stdlib only). Handles pagination from Alchemy, concurrent username resolution via `ThreadPoolExecutor`.
- **`search_usernames_targeted_sherlock.py`** — imports `sherlock_project` from the local submodule at runtime by prepending `./sherlock` to `sys.path`. The `TARGET_SITES` list at the top is the curated set; sites marked "not in Sherlock manifest" will produce warnings but won't fail. `TARGET_SITE_ALIASES` maps display names to Sherlock manifest keys.
- **`site_user_info_scripts/working/`** — standalone per-site scripts that return JSON to stdout. All scripts in this folder are confirmed working.
- **`site_user_info_scripts/not_working/`** — scripts pending implementation, fix, or testing. See `site_user_info_scripts/not_working/CLAUDE.md` for the implementation tracker, status of each script, common bug patterns, and the recommended implementation order. Do not call these from other scripts — move them to `working/` first.
- **`site_user_info_scripts/aggregate_user_info_to_txt.py`** — calls all working scripts concurrently and appends a JSON block per user to a `.txt` file, delimited by `=== USER_INFO_RECORD_START/END ===`.
- **`general_sherlock/run.py`** — batch runner that shells out to `sherlock` CLI for each username in a file and summarizes hits.

### Output

- All results land in `results/` (created automatically). New `.txt` and `targeted_sherlock_results.json` files are git-ignored.
- `get_event_holder_usernames.py` writes two username sections separated by a blank line: Yes-position holders first, then No-position holders.
- Progress and stats go to **stderr**; only the output file path is meaningful stdout.

### Sherlock submodule

The submodule is the upstream `sherlock-project/sherlock` repo. Do not edit files under `sherlock/` directly — changes will conflict on next submodule update. If a site probe needs fixing, add it to `TARGET_SITES` or `TARGET_SITE_ALIASES` in `search_usernames_targeted_sherlock.py` instead.
