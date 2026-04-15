# Site User Info Scripts

This folder contains one script per site to collect user profile information.

## Structure

- `api_friendly/`: sites that can be queried now with public endpoints.
- `api_auth/`: sites that require API key, OAuth, or bearer token.
- `scrape_pending/`: scaffolded scripts for scrape-first sites.

## Implemented Now

Public API friendly scripts:

- `api_friendly/github_user_info.py`
- `api_friendly/hackernews_user_info.py`
- `api_friendly/keybase_user_info.py`
- `api_friendly/chesscom_user_info.py`
- `api_friendly/mixcloud_user_info.py`
- `api_friendly/substack_user_info.py`
- `api_friendly/medium_user_info.py`
- `api_friendly/cashapp_user_info.py`
- `api_friendly/rentry_user_info.py` (paste ID lookup)
- `api_friendly/telegra_ph_user_info.py` (page path lookup)

Auth or API key scripts:

- `api_auth/reddit_user_info.py`
- `api_auth/stackoverflow_user_info.py`
- `api_auth/twitter_user_info.py`

## Usage

Run from the repository root.

Example:

```bash
python3 site_user_info_scripts/api_friendly/github_user_info.py octocat
python3 site_user_info_scripts/api_friendly/hackernews_user_info.py pg
python3 site_user_info_scripts/api_friendly/substack_user_info.py hamishmckenzie
python3 site_user_info_scripts/api_friendly/medium_user_info.py towardsdatascience
python3 site_user_info_scripts/api_auth/stackoverflow_user_info.py jon_skeet
```

Auth examples:

```bash
REDDIT_ACCESS_TOKEN="..." python3 site_user_info_scripts/api_auth/reddit_user_info.py spez
TWITTER_BEARER_TOKEN="..." python3 site_user_info_scripts/api_auth/twitter_user_info.py jack
```

You can also store auth secrets in a `.env` file. The auth scripts and the
aggregate script automatically look for `.env` in the current directory and
walk upward until found.

Example `.env`:

```dotenv
REDDIT_ACCESS_TOKEN=your_reddit_oauth_token
STACKEXCHANGE_API_KEY=your_stackexchange_api_key
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
```

Aggregate all API-based collectors into one structured text record per user:

```bash
python3 site_user_info_scripts/aggregate_user_info_to_txt.py octocat
python3 site_user_info_scripts/aggregate_user_info_to_txt.py octocat --output site_user_info_scripts/user_info_records.txt
REDDIT_ACCESS_TOKEN="..." TWITTER_BEARER_TOKEN="..." python3 site_user_info_scripts/aggregate_user_info_to_txt.py someuser
```

The aggregate script appends each run as one JSON block between:

- `=== USER_INFO_RECORD_START ===`
- `=== USER_INFO_RECORD_END ===`

## Notes

- These scripts are intentionally standalone and return JSON to stdout.
- Rentry and Telegra.ph do not support username-account API lookup. Their scripts resolve by paste ID and page path respectively.
- The scrape-pending scripts are placeholders and output a structured "pending" response.
- You can later swap the pending scripts to BeautifulSoup/Playwright implementations.
