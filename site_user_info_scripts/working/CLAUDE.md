# Working Scripts — Request Methods & Rate Limit Reference

This file documents the data collection methods used by each site-specific user info scraper, including authentication requirements and rate-limit risk assessments. This reference enables implementation of per-site rate-limit counters and intelligent request scheduling.

## scraper_base.py

Provides shared utilities for all scrapers:
- `new_session()`: creates a requests.Session with standard browser headers
- `jitter(lo=0.5, hi=1.5)`: adds random delay between requests
- `safe_text(el)`: safely extracts text from BeautifulSoup elements
- `get_beautifulsoup()`: dynamically imports BeautifulSoup if available
- `dump(obj)`: JSON serialization utility
- `err(site, reason)` and `ok(site, username, data)`: response formatting

## Scripts

### `about_me_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://about.me/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `academia_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{institution}.academia.edu/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `akniga_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://akniga.org/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `allMyLinks_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://allmylinks.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `anilist_user_info.py`
- **Method**: GraphQL
- **Endpoint**: `https://graphql.anilist.co`
- **Auth**: None
- **Rate-limit risk**: Low

### `archive_of_our_own_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://archiveofourown.org/users/{}/profile`
- **Auth**: None
- **Rate-limit risk**: Low

### `atcoder_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://atcoder.jp/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `behance_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.behance.net/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `bitbucket_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.bitbucket.org/2.0/users/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `bitcointalk_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://bitcointalk.org/index.php?action=profile;u={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `blitztactics_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://blitztactics.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `bluesky_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `buymeacoffee_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.buymeacoffee.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `buzzfeed_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.buzzfeed.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `cartalkcommunity_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://community.cartalk.com/u/{}.json`
- **Auth**: None
- **Rate-limit risk**: Low

### `cashapp_user_info.py`
- **Method**: Headless browser
- **Endpoint**: `https://cash.app/${}`
- **Auth**: None
- **Rate-limit risk**: Low

### `championat_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.championat.com/user/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `chesscom_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.chess.com/pub/player/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `chollometro_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.chollometro.com/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `codechef_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.codechef.com/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `codeforces_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://codeforces.com/api/user.info?handles={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `codepen_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://codepen.io/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `codersrank_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://profile.codersrank.io/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `coderwall_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://coderwall.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `codewars_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://www.codewars.com/api/v1/users/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `couchsurfing_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.couchsurfing.com/people/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `crowdin_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://crowdin.com/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `d3ru_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://d3.ru/user/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `dailymotion_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.dailymotion.com/user/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `dcinside_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://gallog.dcinside.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `dealabs_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.dealabs.com/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `dev_community_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://dev.to/api/users/by_username?url={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `discogs_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.discogs.com/users/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `dockerhub_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://hub.docker.com/v2/users/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `dribbble_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://dribbble.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `drive2_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.drive2.ru/users/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `duolingo_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://www.duolingo.com/2017-06-30/users?username={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `facebook_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.facebook.com/{}`
- **Auth**: None
- **Rate-limit risk**: High

### `flickr_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.flickr.com/people/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `flipboard_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://flipboard.com/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `furaffinity_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.furaffinity.net/user/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `gaiaonline_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.gaiaonline.com/profiles/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `gitee_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://gitee.com/api/v5/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `github_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.github.com/users/{}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `gitlab_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://gitlab.com/api/v4/users?username={}`
- **Auth**: None
- **Rate-limit risk**: Medium

### `goodreads_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.goodreads.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `grailed_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.grailed.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `gumroad_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://gumroad.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `gutefrage_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.gutefrage.net/nutzer/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `habr_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://habr.com/en/users/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `hackernews_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://hacker-news.firebaseio.com/v0/user/{}.json`
- **Auth**: None
- **Rate-limit risk**: Low

### `hackerone_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://hackerone.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `hackmd_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://hackmd.io/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `hive_blog_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://api.hive.blog (JSON-RPC)`
- **Auth**: None
- **Rate-limit risk**: Low

### `houzz_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.houzz.com/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `hudsonrock_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://cavalier.hudsonrock.com/api/json/v2/osint-tools/search-by-username?username={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `huggingface_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://huggingface.co/api/users/{}/overview`
- **Auth**: None
- **Rate-limit risk**: Low

### `itch_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.itch.io`
- **Auth**: None
- **Rate-limit risk**: Low

### `keybase_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://keybase.io/_/api/1.0/user/lookup.json?usernames={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `kongregate_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.kongregate.com/accounts/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `kwork_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://kwork.ru/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `lastfm_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.last.fm/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `launchpad_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.launchpad.net/1.0/~{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `leetcode_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://leetcode.com/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `lemmyworld_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://lemmy.world/api/v3/user?username={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `letterboxd_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://letterboxd.com/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `lichess_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://lichess.org/api/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `linktree_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://linktr.ee/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `linuxfr_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://linuxfr.org/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `livejournal_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.livejournal.com`
- **Auth**: None
- **Rate-limit risk**: Low

### `mamot_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://mamot.fr/api/v1/accounts/lookup?acct={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `mastodon_cloud_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://mastodon.cloud/api/v1/accounts/lookup?acct={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `mastodon_social_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://mastodon.social/api/v1/accounts/lookup?acct={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `medium_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://medium.com/feed/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `mixcloud_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.mixcloud.com/{}/`
- **Auth**: None
- **Rate-limit risk**: Medium

### `monkeytype_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.monkeytype.com/users/{}/profile`
- **Auth**: None
- **Rate-limit risk**: Low

### `myanimelist_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.jikan.moe/v4/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `mydealz_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.mydealz.de/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `naver_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://blog.naver.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `nintendolife_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.nintendolife.com/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `note_jp_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://note.com/api/v2/creators/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `odysee_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://odysee.com/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `omg_lol_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.omg.lol/address/{}/info`
- **Auth**: None
- **Rate-limit risk**: Low

### `opencollective_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://opencollective.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `osu_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://osu.ppy.sh/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `packagist_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://packagist.org/users/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `pastebin_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://pastebin.com/u/{}`
- **Auth**: `PASTEBIN_API_KEY`
- **Rate-limit risk**: Low

### `pastebin_user_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://pastebin.com/u/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `pepperpl_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.pepper.pl/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `pikabu_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://pikabu.ru/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `plurk_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.plurk.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `pokemon_showdown_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://pokemonshowdown.com/users/{}.json`
- **Auth**: None
- **Rate-limit risk**: Low

### `producthunt_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.producthunt.com/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `promodescuentos_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.promodescuentos.com/profile/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `quora_user_info.py`
- **Method**: Headless browser
- **Endpoint**: `https://www.quora.com/profile/{}`
- **Auth**: `QUORA_M_B`
- **Rate-limit risk**: Low

### `rajce_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.rajce.idnes.cz/`
- **Auth**: None
- **Rate-limit risk**: Low

### `replit_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://replit.com/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `reverbnation_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.reverbnation.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `runescape_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://apps.runescape.com/runemetrics/profile/profile?user={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `scratch_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://api.scratch.mit.edu/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `sketchfab_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://sketchfab.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `snapchat_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.snapchat.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `soundcloud_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://soundcloud.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `speakerdeck_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://speakerdeck.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `speedrun_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://www.speedrun.com/api/v1/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `star_citizen_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://robertsspaceindustries.com/citizens/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `steam_group_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://steamcommunity.com/groups/{}/memberslistxml/?xml=1`
- **Auth**: None
- **Rate-limit risk**: Low

### `steam_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://steamcommunity.com/id/{}/?xml=1`
- **Auth**: None
- **Rate-limit risk**: Low

### `sublimeforum_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://forum.sublimetext.com/u/{}.json`
- **Auth**: None
- **Rate-limit risk**: Low

### `substack_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://substack.com/@{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `swapd_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://swapd.co/u/{}.json`
- **Auth**: None
- **Rate-limit risk**: Low

### `telegram_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://t.me/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `tetrio_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://ch.tetr.io/api/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `tiendanube_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.tiendanube.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `tistory_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.tistory.com`
- **Auth**: None
- **Rate-limit risk**: Low

### `tradingview_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.tradingview.com/u/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `tumblr_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.tumblr.com`
- **Auth**: None
- **Rate-limit risk**: Low

### `tuna_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://tuna.voiceofrussia.com/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `typeracer_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://data.typeracer.com/pit/profile?user={}`
- **Auth**: None
- **Rate-limit risk**: Low

### `ultimate_guitar_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.ultimate-guitar.com/u/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `untappd_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://untappd.com/user/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `warrior_forum_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.warriorforum.com/members/{}.html`
- **Auth**: None
- **Rate-limit risk**: Low

### `wattpad_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://www.wattpad.com/api/v3/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `weebly_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://{}.weebly.com`
- **Auth**: None
- **Rate-limit risk**: Low

### `wikidot_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.wikidot.com/user:info/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `wikipedia_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://{lang}.wikipedia.org/wiki/User:{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `wordpress_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://public-api.wordpress.com/rest/v1.1/sites/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `write_as_user_info.py`
- **Method**: Official API
- **Endpoint**: `https://write.as/api/collections/{}`
- **Auth**: None
- **Rate-limit risk**: Low

### `wykop_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://www.wykop.pl/ludzie/{}/`
- **Auth**: None
- **Rate-limit risk**: Low

### `youknowmeme_user_info.py`
- **Method**: HTML scrape
- **Endpoint**: `https://knowyourmeme.com/users/{}`
- **Auth**: None
- **Rate-limit risk**: Low

