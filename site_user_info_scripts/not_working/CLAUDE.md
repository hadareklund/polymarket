# not_working/ — Implementation Tracker

Scripts here are stubs or broken implementations awaiting implementation, fix, and testing.
**Workflow**: implement → test with a real username → move to `../working/` when confirmed.

## Common issues in existing stubs

Most stubs share a Python **syntax error**: `["']` inside single-quoted raw strings breaks the string literal early. Fix by using double-quoted outer strings:

```python
# Broken
re.search(r'<meta[^>]+name=["']foo["']...', html)

# Fixed — use a _meta() helper instead
def _meta(html, name, attr="name"):
    for pattern in [
        rf'<meta\s[^>]*{re.escape(attr)}="{re.escape(name)}"[^>]*content="([^"]*)"',
        rf'<meta\s[^>]*content="([^"]*)"[^>]*{re.escape(attr)}="{re.escape(name)}"',
    ]:
        m = re.search(pattern, html, re.I)
        if m:
            return m.group(1).strip()
    return None
```

Also check for JSON-LD embedded in `<script type="application/ld+json">` — richer than meta tags.

## Status legend

| Symbol | Meaning |
|--------|---------|
| ✅ done | Implemented, tested, moved to `working/` |
| 🔧 in progress | Currently being worked on |
| ❌ blocked | Site blocks bots / requires auth / JS-only |
| ⬜ pending | Not yet started |

## Completed (moved to working/)

| Script | Notes |
|--------|-------|
| about_me_user_info.py | ✅ OG + JSON-LD. Returns name, description, avatar. |
| academia_user_info.py | ✅ Requires `--institution` flag (default: `independent`). Profiles at `<institution>.academia.edu/<Name>`. |
| akniga_user_info.py | ✅ OG + JSON-LD. Russian audiobook site. book/review counts not in OG — extracted via body regex (may be null). |
| allMyLinks_user_info.py | ✅ OG + JSON-LD. Note: actual profile links are JS-rendered and unavailable in static HTML. |
| anilist_user_info.py | ✅ Public GraphQL API. Returns full anime/manga stats and favourites. |

## Pending scripts (~170 remaining)

All files in this directory are pending unless listed above. Alphabetical order is a reasonable implementation order — prioritize sites with public APIs (JSON/GraphQL) over pure HTML scrapers, and skip anything in `really_not_working/` (those have architectural blockers documented in `really_not_working/WHY_NOT_WORKING.txt`).

### High-value / API-friendly (implement next)

| Script | Site | Method |
|--------|------|--------|
| bluesky_user_info.py | Bluesky | Public AT Protocol API (`public.api.bsky.app`) |
| codeforces_user_info.py | Codeforces | Public REST API |
| codewars_user_info.py | Codewars | Public REST API |
| dockerhub_user_info.py | Docker Hub | Public REST API |
| duolingo_user_info.py | Duolingo | Public REST API |
| gitlab_user_info.py | GitLab | Public REST API |
| huggingface_user_info.py | Hugging Face | Public REST API |
| lastfm_user_info.py | Last.fm | Public REST API |
| leetcode_user_info.py | LeetCode | GraphQL API |
| letterboxd_user_info.py | Letterboxd | HTML + JSON-LD |
| lichess_user_info.py | Lichess | Public REST API |
| myanimelist_user_info.py | MyAnimeList | Public REST API (Jikan) |
| npm_user_info.py | npm | Public REST API |
| osu_user_info.py | osu! | Public REST API |
| producthunt_user_info.py | Product Hunt | GraphQL API |
| runescape_user_info.py | RuneScape | Public REST API |
| speedrun_user_info.py | Speedrun.com | Public REST API |
| steam_user_info.py | Steam | Public REST API |
| trakt_user_info.py | Trakt | Public REST API |
| twitch_user_info.py | Twitch | REST API (client-id required) |

### HTML scrapers (implement after API-friendly batch)

Scripts not listed above that use HTML scraping — fix the regex syntax error and verify the site doesn't block bots.

### really_not_working/

These have fundamental blockers (Cloudflare, login walls, anti-bot 403/999). See `really_not_working/WHY_NOT_WORKING.txt` for details. Do not attempt without Playwright/auth tokens.
