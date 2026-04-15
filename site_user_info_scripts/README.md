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
python3 site_user_info_scripts/api_auth/stackoverflow_user_info.py jon_skeet
```

Auth examples:

```bash
REDDIT_ACCESS_TOKEN="..." python3 site_user_info_scripts/api_auth/reddit_user_info.py spez
TWITTER_BEARER_TOKEN="..." python3 site_user_info_scripts/api_auth/twitter_user_info.py jack
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
- The scrape-pending scripts are placeholders and output a structured "pending" response.
- You can later swap the pending scripts to BeautifulSoup/Playwright implementations.
