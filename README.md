# polymarket

Small utility scripts for collecting Polymarket holder/user information and running targeted username checks.

## Repository Contents

- `get_event_holder_usernames.py`  
  Fetches full holder wallets for a Polymarket event market and resolves usernames using public APIs.
- `search_usernames_targeted_sherlock.py`  
  Runs a targeted site list through a local Sherlock checkout and writes JSON results.
- `site_user_info_scripts/`  
  Site-specific profile lookup scripts (see `/home/runner/work/polymarket/polymarket/site_user_info_scripts/README.md`).

## Prerequisites

- Python 3.10+
- `git` (for submodule setup)

For Sherlock-based searches, initialize the Sherlock submodule:

```bash
git submodule update --init --recursive
```

## Usage

Run from the repository root.

### 1) Fetch event holders and resolve usernames

```bash
python3 get_event_holder_usernames.py "https://polymarket.com/event/<event-slug>"
```

Useful options:

- `--alchemy-api-key <key>` (or set `ALCHEMY_API_KEY`)
- `--workers <n>`
- `--wallet-fallback`
- `--exclude-zero-address`
- `--output <path>`

### 2) Targeted Sherlock username search

```bash
python3 search_usernames_targeted_sherlock.py username1 username2
```

Useful options:

- `--usernames-file <path>`
- `--output <path>` (default: `targeted_sherlock_results.json`)
- `--timeout <seconds>`
- `--print-all`

If Sherlock import dependencies are missing, install them from the local submodule:

```bash
python3 -m pip install -e ./sherlock
```

### 3) Site-specific user info scripts

See `/home/runner/work/polymarket/polymarket/site_user_info_scripts/README.md` for script list and examples.

## Output Notes

- Newly generated, untracked text and JSON outputs are ignored by git (`*.txt`, `targeted_sherlock_results.json`); files already tracked by git are not affected by ignore rules.
- Environment files (`.env*`) are also ignored.
