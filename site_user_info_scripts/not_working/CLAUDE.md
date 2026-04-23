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
| mamot_user_info.py | ✅ Mastodon API (`/api/v1/accounts/lookup`). Returns followers, posts, bio. |
| mastodon_cloud_user_info.py | ✅ Mastodon API (`/api/v1/accounts/lookup`). Returns followers, posts, bio. |
| mastodon_social_user_info.py | ✅ Mastodon API (`/api/v1/accounts/lookup`). Returns followers, posts, bio. |
| memrise_user_info.py | ❌ Moved to `really_not_working/` — Next.js SPA, no public API, login required. |
| monkeytype_user_info.py | ✅ Public REST API. Returns typing stats, best WPM, streak, XP. |
| hackmd_user_info.py | ✅ HTML scraper. Extracts display name from og:title. Avatar is generic site image. |
| hackster_user_info.py | ❌ Moved to `really_not_working/` — React SPA, no server-rendered profile, API requires auth. |
| hive_blog_user_info.py | ✅ Blockchain JSON-RPC API. Returns display name, bio, location, avatar, post count. |
| houzz_user_info.py | ✅ HTML + embedded JS store. Parses UserProfileStore JSON for display name and stats. |
| hudsonrock_user_info.py | ✅ Public REST API. Returns infostealer exposure: compromised flag, stealer count, OS/IP. |
| packagist_user_info.py | ✅ Public packages list API. Returns all vendor packages and count. |
| pastebin_user_user_info.py | ✅ HTML scraper. Returns display name, avatar, profile views, join date. |
| patreon_user_info.py | ❌ Moved to `really_not_working/` — Next.js SPA, all OG tags are generic, OAuth required for API. |
| peppernl_user_info.py | ❌ Moved to `really_not_working/` — site is unreachable (HTTP 000/connection refused). |
| pepperpl_user_info.py | ✅ HTML scraper using `window.__INITIAL_STATE__` JSON. Returns stats, badges, join date. |
| pikabu_user_info.py | ✅ HTML scraper with windows-1251 charset detection. Parses og:description for post/comment/follower counts. |
| pinkbike_user_info.py | ❌ Moved to `really_not_working/` — Cloudflare (HTTP 403 JS challenge), no public API. |
| pinterest_user_info.py | ❌ Moved to `really_not_working/` — React SPA, login required, no public API. |
| plurk_user_info.py | ✅ HTML scraper + extracts `page_user` block from embedded JS (GLOBAL var). Returns display name, karma, location, avatar. |
| pokemon_showdown_user_info.py | ✅ Public JSON API. Returns username, avatar, registration date, ladder ratings per format. |
| redbubble_user_info.py | ❌ Moved to `really_not_working/` — Cloudflare JS challenge (HTTP 403), no public API. |
| replit_user_info.py | ✅ HTML scraper. Fixed regex syntax errors. Returns display name, description, avatar from OG tags. |
| reverbnation_user_info.py | ✅ HTML scraper. Fixed regex syntax errors. Returns display name, description, avatar from OG tags. |
| runescape_user_info.py | ✅ Public REST API (RuneMetrics). Returns total XP, level, combat level, quests. |
| scratch_user_info.py | ✅ Public REST API (api.scratch.mit.edu). Returns bio, status, country, avatar, join date. |
| sketchfab_user_info.py | ✅ HTML scraper (sketchfab.com/{username}). Returns display name, bio, avatar (from embedded React bundle). |
| slack_user_info.py | ❌ Moved to `really_not_working/` — no public profile pages; all profiles require workspace membership. |
| snapchat_user_info.py | ✅ HTML scraper (snapchat.com/add/{username}). Returns display name, avatar, snapcode URL from embedded JSON + OG tags. |
| soop_user_info.py | ❌ Moved to `really_not_working/` — bare Next.js SPA, no OG tags; API requires proprietary partner token. |
| soundcloud_user_info.py | ✅ HTML scraper (soundcloud.com/{username}). Returns display name, bio, avatar, follower/track/playlist counts from embedded JSON. |
| kaskus_user_info.py | ❌ Moved to `really_not_working/` — Next.js SPA, generic OG tags only, no public API. |
| kick_user_info.py | ❌ Moved to `really_not_working/` — JS SPA, API requires authenticated session token. |
| kofi_user_info.py | ❌ Moved to `really_not_working/` — Cloudflare managed JS challenge on all requests. |
| kongregate_user_info.py | ✅ HTML scraper. Returns display name, level, points, badges, fans, friends, avatar. |
| kwork_user_info.py | ✅ HTML scraper. Returns display name (from title), description, avatar from meta tags. |
| launchpad_user_info.py | ✅ Public REST API (api.launchpad.net/1.0). Returns display name, bio, timezone, karma, join date. |
| lemmyworld_user_info.py | ✅ Public REST API (lemmy.world/api/v3). Returns bio, avatar, post/comment counts, join date. |
| linktree_user_info.py | ✅ HTML scraper (OG meta tags). Returns display name, bio, avatar. |
| linuxfr_user_info.py | ✅ HTML scraper. Returns content count (from title), avatar. |
| livejournal_user_info.py | ✅ HTML scraper (JSON-LD + Site.page). Returns real name, journal title, journal URL, avatar, achievements. |

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
