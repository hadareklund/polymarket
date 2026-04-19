#!/usr/bin/env python3
"""
Generate user-info scraper stubs for all sites in the stats file.
Run: python3 generate_scrapers.py
Creates one *_user_info.py per site in site_user_info_scripts/not_working/.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

OUT = Path(__file__).resolve().parent / "site_user_info_scripts" / "not_working"

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_HEADER = '''\
#!/usr/bin/env python3
"""{docstring}"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json
'''

_MAIN_WRAP = '''

def main() -> int:
    parser = argparse.ArgumentParser(description="Get {name} user info by username.")
    parser.add_argument("username", help="{name} username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
{body}
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {{exc}}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def _pub(name, api_url, profile_url, extract_lines):
    """Public JSON API — no auth."""
    body_lines = [
        f'        data = fetch_json(f"{api_url}", timeout=args.timeout)',
    ] + ["        " + l for l in extract_lines]
    body = "\n".join(body_lines)
    return (
        _HEADER.format(docstring=f"Fetch user profile information from {name}.") +
        _MAIN_WRAP.format(name=name, body=body)
    )


def _apikey(name, api_url, profile_url, env_var, auth_param, extract_lines, extra_imports=""):
    """API key required — from env."""
    extra = f"\nimport os\n{extra_imports}" if extra_imports else "\nimport os"
    body_lines = [
        f'        key = os.environ.get("{env_var}", "")',
        f'        if not key:',
        f'            raise RuntimeError("{env_var} not set in environment.")',
        f'        url = f"{api_url}"',
        f'        data = fetch_json(url, headers={{"{auth_param[0]}": f"{auth_param[1]}"}}, timeout=args.timeout)',
    ] + ["        " + l for l in extract_lines]
    body = "\n".join(body_lines)
    return (
        _HEADER.format(docstring=f"Fetch user profile information from {name} (requires API key).") +
        extra + "\n" +
        _MAIN_WRAP.format(name=name, body=body)
    )


def _html(name, profile_url, extra_imports="", extra_code=""):
    """Best-effort HTML scraper."""
    extra = f"\nimport re\n{extra_imports}" if extra_imports else "\nimport re"
    body = textwrap.dedent(f"""\
        from common import fetch_text
        url = f"{profile_url}"
        html = fetch_text(url, headers={{"User-Agent": "Mozilla/5.0"}}, timeout=args.timeout)
        if len(html) < 500:
            raise RuntimeError("Empty or blocked response.")
        title_m = re.search(r"<title[^>]*>([^<]+)</title>", html, re.I)
        desc_m = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)', html, re.I)
        og_title = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)', html, re.I)
        og_image = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html, re.I)
{extra_code}        result = {{
            "site": "{name}",
            "username": args.username,
            "title": og_title.group(1).strip() if og_title else (title_m.group(1).strip() if title_m else None),
            "description": desc_m.group(1).strip() if desc_m else None,
            "avatar_url": og_image.group(1).strip() if og_image else None,
            "profile_url": url,
        }}""").splitlines()
    body = "\n".join("        " + l for l in body)
    return (
        _HEADER.format(docstring=f"Fetch user profile information from {name} (HTML scraper).") +
        extra + "\n" +
        _MAIN_WRAP.format(name=name, body=body)
    )


def _graphql(name, endpoint, query_tpl, profile_url, extract_lines):
    """GraphQL scraper."""
    body_lines = [
        "        import json as _json",
        "        from urllib.request import Request, urlopen",
        f'        query = """{query_tpl}"""',
        f'        payload = _json.dumps({{"query": query, "variables": {{"username": args.username}}}}).encode()',
        f'        req = Request("{endpoint}", data=payload, headers={{"Content-Type": "application/json", "User-Agent": "site-user-info-scripts/1.0"}})',
        "        with urlopen(req, timeout=args.timeout) as r:",
        "            data = _json.loads(r.read().decode())",
    ] + ["        " + l for l in extract_lines]
    body = "\n".join(body_lines)
    return (
        _HEADER.format(docstring=f"Fetch user profile information from {name} (GraphQL).") +
        _MAIN_WRAP.format(name=name, body=body)
    )


def _blocked(name, reason, profile_url=""):
    """Stub for sites that can't be scraped without auth/Playwright."""
    body = textwrap.dedent(f"""\
        raise RuntimeError(
            "{name} cannot be scraped automatically: {reason}"
        )
        result = {{}}  # unreachable""").splitlines()
    body_str = "\n".join("        " + l for l in body)
    return (
        _HEADER.format(docstring=f"{name} — not scrapeable: {reason}") +
        _MAIN_WRAP.format(name=name, body=body_str)
    )


# ---------------------------------------------------------------------------
# Site definitions  (slug → code)
# ---------------------------------------------------------------------------

def build_all() -> dict[str, str]:
    sites: dict[str, str] = {}

    def add(slug: str, code: str) -> None:
        sites[slug] = code

    # -----------------------------------------------------------------------
    # Public JSON APIs
    # -----------------------------------------------------------------------

    add("duolingo", _pub("Duolingo",
        "https://www.duolingo.com/2017-06-30/users?username={args.username}",
        "https://www.duolingo.com/profile/{args.username}",
        [
            'users = data.get("users") or []',
            'if not users: raise RuntimeError("User not found.")',
            'u = users[0]',
            'result = {',
            '    "site": "Duolingo",',
            '    "username": u.get("username"),',
            '    "display_name": u.get("name"),',
            '    "bio": u.get("bio"),',
            '    "total_xp": u.get("totalXp"),',
            '    "streak": u.get("streak"),',
            '    "courses": [c.get("title") for c in (u.get("courses") or [])],',
            '    "followers": u.get("followers"),',
            '    "following": u.get("following"),',
            '    "profile_url": f"https://www.duolingo.com/profile/{args.username}",',
            '}',
        ]))

    add("scratch", _pub("Scratch",
        "https://api.scratch.mit.edu/users/{args.username}",
        "https://scratch.mit.edu/users/{args.username}/",
        [
            'if "id" not in data: raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "Scratch",',
            '    "username": data.get("username"),',
            '    "display_name": data.get("profile", {}).get("bio"),',
            '    "bio": data.get("profile", {}).get("bio"),',
            '    "country": data.get("profile", {}).get("country"),',
            '    "joined": data.get("history", {}).get("joined"),',
            '    "profile_url": f"https://scratch.mit.edu/users/{args.username}/",',
            '}',
        ]))

    add("bluesky", _pub("Bluesky",
        "https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor={args.username}",
        "https://bsky.app/profile/{args.username}",
        [
            'if "error" in data: raise RuntimeError(data.get("message", "Not found."))',
            'result = {',
            '    "site": "Bluesky",',
            '    "username": data.get("handle"),',
            '    "display_name": data.get("displayName"),',
            '    "bio": data.get("description"),',
            '    "followers": data.get("followersCount"),',
            '    "following": data.get("followsCount"),',
            '    "posts": data.get("postsCount"),',
            '    "avatar_url": data.get("avatar"),',
            '    "profile_url": f"https://bsky.app/profile/{args.username}",',
            '}',
        ]))

    add("huggingface", _pub("Hugging Face",
        "https://huggingface.co/api/users/{args.username}",
        "https://huggingface.co/{args.username}",
        [
            'if "error" in data: raise RuntimeError(data.get("error", "Not found."))',
            'result = {',
            '    "site": "Hugging Face",',
            '    "username": data.get("name"),',
            '    "full_name": data.get("fullname"),',
            '    "bio": data.get("details"),',
            '    "location": data.get("location"),',
            '    "website": data.get("websiteUrl"),',
            '    "followers": data.get("numFollowers"),',
            '    "models": data.get("numModels"),',
            '    "datasets": data.get("numDatasets"),',
            '    "spaces": data.get("numSpaces"),',
            '    "profile_url": f"https://huggingface.co/{args.username}",',
            '}',
        ]))

    add("lichess", _pub("Lichess",
        "https://lichess.org/api/user/{args.username}",
        "https://lichess.org/@/{args.username}",
        [
            'if "error" in data: raise RuntimeError(data["error"])',
            'perf = data.get("perfs") or {}',
            'result = {',
            '    "site": "Lichess",',
            '    "username": data.get("username"),',
            '    "title": data.get("title"),',
            '    "bio": (data.get("profile") or {}).get("bio"),',
            '    "country": (data.get("profile") or {}).get("country"),',
            '    "location": (data.get("profile") or {}).get("location"),',
            '    "real_name": (data.get("profile") or {}).get("realName"),',
            '    "followers": data.get("nbFollowers"),',
            '    "following": data.get("nbFollowing"),',
            '    "games_played": (data.get("count") or {}).get("all"),',
            '    "rating_bullet": (perf.get("bullet") or {}).get("rating"),',
            '    "rating_blitz": (perf.get("blitz") or {}).get("rating"),',
            '    "rating_rapid": (perf.get("rapid") or {}).get("rating"),',
            '    "created_at": data.get("createdAt"),',
            '    "profile_url": f"https://lichess.org/@/{args.username}",',
            '}',
        ]))

    add("pokemon_showdown", _pub("Pokemon Showdown",
        "https://pokemonshowdown.com/users/{args.username}.json",
        "https://pokemonshowdown.com/users/{args.username}",
        [
            'if not data.get("userid"): raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "Pokemon Showdown",',
            '    "username": data.get("name"),',
            '    "userid": data.get("userid"),',
            '    "avatar": data.get("avatar"),',
            '    "profile_url": f"https://pokemonshowdown.com/users/{args.username}",',
            '}',
        ]))

    add("gitlab", _pub("GitLab",
        "https://gitlab.com/api/v4/users?username={args.username}",
        "https://gitlab.com/{args.username}",
        [
            'users = data if isinstance(data, list) else []',
            'if not users: raise RuntimeError("User not found.")',
            'u = users[0]',
            'result = {',
            '    "site": "GitLab",',
            '    "username": u.get("username"),',
            '    "name": u.get("name"),',
            '    "bio": u.get("bio"),',
            '    "location": u.get("location"),',
            '    "website": u.get("website_url"),',
            '    "avatar_url": u.get("avatar_url"),',
            '    "followers": u.get("followers"),',
            '    "following": u.get("following"),',
            '    "public_repos": u.get("public_repos"),',
            '    "created_at": u.get("created_at"),',
            '    "profile_url": u.get("web_url"),',
            '}',
        ]))

    add("bitbucket", _pub("BitBucket",
        "https://api.bitbucket.org/2.0/users/{args.username}",
        "https://bitbucket.org/{args.username}/",
        [
            'if "error" in data: raise RuntimeError(str(data["error"]))',
            'result = {',
            '    "site": "BitBucket",',
            '    "username": data.get("nickname"),',
            '    "display_name": data.get("display_name"),',
            '    "bio": data.get("description"),',
            '    "location": data.get("location"),',
            '    "website": data.get("website"),',
            '    "account_status": data.get("account_status"),',
            '    "created_on": data.get("created_on"),',
            '    "profile_url": (data.get("links") or {}).get("html", {}).get("href"),',
            '}',
        ]))

    add("codewars", _pub("Codewars",
        "https://www.codewars.com/api/v1/users/{args.username}",
        "https://www.codewars.com/users/{args.username}",
        [
            'if data.get("reason") == "not found": raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "Codewars",',
            '    "username": data.get("username"),',
            '    "name": data.get("name"),',
            '    "honor": data.get("honor"),',
            '    "clan": data.get("clan"),',
            '    "city": data.get("city"),',
            '    "rank": (data.get("ranks") or {}).get("overall", {}).get("name"),',
            '    "leaderboard_position": data.get("leaderboardPosition"),',
            '    "languages": list((data.get("ranks") or {}).get("languages", {}).keys()),',
            '    "profile_url": f"https://www.codewars.com/users/{args.username}",',
            '}',
        ]))

    add("dev_community", _pub("DEV Community",
        "https://dev.to/api/users/by_username?url={args.username}",
        "https://dev.to/{args.username}",
        [
            'if "error" in data: raise RuntimeError(data.get("error", "Not found."))',
            'result = {',
            '    "site": "DEV Community",',
            '    "username": data.get("username"),',
            '    "name": data.get("name"),',
            '    "bio": data.get("summary"),',
            '    "location": data.get("location"),',
            '    "website": data.get("website_url"),',
            '    "twitter": data.get("twitter_username"),',
            '    "github": data.get("github_username"),',
            '    "followers": data.get("followers_count"),',
            '    "joined": data.get("joined_at"),',
            '    "profile_url": f"https://dev.to/{args.username}",',
            '}',
        ]))

    add("sketchfab", _pub("Sketchfab",
        "https://api.sketchfab.com/v3/users/{args.username}",
        "https://sketchfab.com/{args.username}",
        [
            'if "detail" in data: raise RuntimeError(data["detail"])',
            'result = {',
            '    "site": "Sketchfab",',
            '    "username": data.get("username"),',
            '    "display_name": data.get("displayName"),',
            '    "bio": data.get("biography"),',
            '    "website": data.get("website"),',
            '    "followers": data.get("followerCount"),',
            '    "following": data.get("followingCount"),',
            '    "model_count": data.get("modelCount"),',
            '    "profile_url": (data.get("profileUrl") or f"https://sketchfab.com/{args.username}"),',
            '}',
        ]))

    add("dockerhub", _pub("Docker Hub",
        "https://hub.docker.com/v2/users/{args.username}/",
        "https://hub.docker.com/u/{args.username}",
        [
            'if data.get("detail") == "Not found.": raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "Docker Hub",',
            '    "username": data.get("username"),',
            '    "full_name": data.get("full_name"),',
            '    "bio": data.get("biography"),',
            '    "location": data.get("location"),',
            '    "company": data.get("company"),',
            '    "date_joined": data.get("date_joined"),',
            '    "profile_url": f"https://hub.docker.com/u/{args.username}",',
            '}',
        ]))

    add("discogs", _pub("Discogs",
        "https://api.discogs.com/users/{args.username}",
        "https://www.discogs.com/user/{args.username}",
        [
            'if "message" in data: raise RuntimeError(data["message"])',
            'result = {',
            '    "site": "Discogs",',
            '    "username": data.get("username"),',
            '    "real_name": data.get("name"),',
            '    "location": data.get("location"),',
            '    "profile": data.get("profile"),',
            '    "followers": data.get("num_collection"),',
            '    "wantlist": data.get("num_wantlist"),',
            '    "registered": data.get("registered"),',
            '    "profile_url": data.get("uri"),',
            '}',
        ]))

    add("tetrio", _pub("TETR.IO",
        "https://ch.tetr.io/api/users/{args.username}",
        "https://tetr.io/u/{args.username}",
        [
            'if not data.get("success"): raise RuntimeError(data.get("error", {}).get("msg", "Not found."))',
            'u = data.get("data") or {}',
            'result = {',
            '    "site": "TETR.IO",',
            '    "username": u.get("username"),',
            '    "xp": u.get("xp"),',
            '    "country": u.get("country"),',
            '    "supporter": u.get("supporter"),',
            '    "verified": u.get("verified"),',
            '    "profile_url": f"https://tetr.io/u/{args.username}",',
            '}',
        ]))

    add("speedrun", _pub("Speedrun.com",
        "https://www.speedrun.com/api/v1/users/{args.username}",
        "https://www.speedrun.com/user/{args.username}",
        [
            'u = (data.get("data") or {})',
            'if not u: raise RuntimeError("User not found.")',
            'names = u.get("names") or {}',
            'result = {',
            '    "site": "Speedrun.com",',
            '    "username": names.get("international"),',
            '    "location": (u.get("location") or {}).get("country", {}).get("names", {}).get("international"),',
            '    "twitch": (u.get("twitch") or {}).get("uri"),',
            '    "youtube": (u.get("youtube") or {}).get("uri"),',
            '    "twitter": (u.get("twitter") or {}).get("uri"),',
            '    "signup": u.get("signup"),',
            '    "profile_url": (u.get("weblink") or f"https://www.speedrun.com/user/{args.username}"),',
            '}',
        ]))

    add("runescape", _pub("RuneScape",
        "https://apps.runescape.com/runemetrics/profile/profile?user={args.username}&activities=0",
        "https://apps.runescape.com/runemetrics/app/overview/player/{args.username}",
        [
            'if data.get("error"): raise RuntimeError(data["error"])',
            'result = {',
            '    "site": "RuneScape",',
            '    "username": data.get("name"),',
            '    "rank": data.get("rank"),',
            '    "total_xp": data.get("totalxp"),',
            '    "total_level": data.get("totalskill"),',
            '    "combat_level": data.get("combatlevel"),',
            '    "quests_complete": data.get("questscomplete"),',
            '    "profile_url": f"https://apps.runescape.com/runemetrics/app/overview/player/{args.username}",',
            '}',
        ]))

    add("dailymotion", _pub("DailyMotion",
        "https://api.dailymotion.com/user/{args.username}?fields=id,url,username,screenname,description,avatar_720_url,followers_total,following_total,videos_total,created_time",
        "https://www.dailymotion.com/{args.username}",
        [
            'if "error" in data: raise RuntimeError(str(data["error"]))',
            'result = {',
            '    "site": "DailyMotion",',
            '    "username": data.get("username"),',
            '    "display_name": data.get("screenname"),',
            '    "bio": data.get("description"),',
            '    "avatar_url": data.get("avatar_720_url"),',
            '    "followers": data.get("followers_total"),',
            '    "following": data.get("following_total"),',
            '    "videos": data.get("videos_total"),',
            '    "created_at": data.get("created_time"),',
            '    "profile_url": data.get("url"),',
            '}',
        ]))

    add("gitee", _pub("Gitee",
        "https://gitee.com/api/v5/users/{args.username}",
        "https://gitee.com/{args.username}",
        [
            'if "message" in data: raise RuntimeError(data["message"])',
            'result = {',
            '    "site": "Gitee",',
            '    "username": data.get("login"),',
            '    "name": data.get("name"),',
            '    "bio": data.get("bio"),',
            '    "blog": data.get("blog"),',
            '    "public_repos": data.get("public_repos"),',
            '    "followers": data.get("followers"),',
            '    "following": data.get("following"),',
            '    "created_at": data.get("created_at"),',
            '    "profile_url": data.get("html_url"),',
            '}',
        ]))

    add("launchpad", _pub("Launchpad",
        "https://api.launchpad.net/1.0/~{args.username}",
        "https://launchpad.net/~{args.username}",
        [
            'if "message" in data: raise RuntimeError(data["message"])',
            'result = {',
            '    "site": "Launchpad",',
            '    "username": data.get("name"),',
            '    "display_name": data.get("display_name"),',
            '    "bio": data.get("description"),',
            '    "location": data.get("location"),',
            '    "time_zone": data.get("time_zone"),',
            '    "karma": data.get("karma"),',
            '    "profile_url": data.get("web_link"),',
            '}',
        ]))

    add("codeforces", _pub("Codeforces",
        "https://codeforces.com/api/user.info?handles={args.username}",
        "https://codeforces.com/profile/{args.username}",
        [
            'if data.get("status") != "OK": raise RuntimeError(data.get("comment", "Not found."))',
            'u = (data.get("result") or [{}])[0]',
            'result = {',
            '    "site": "Codeforces",',
            '    "username": u.get("handle"),',
            '    "rank": u.get("rank"),',
            '    "max_rank": u.get("maxRank"),',
            '    "rating": u.get("rating"),',
            '    "max_rating": u.get("maxRating"),',
            '    "country": u.get("country"),',
            '    "city": u.get("city"),',
            '    "organization": u.get("organization"),',
            '    "contribution": u.get("contribution"),',
            '    "profile_url": f"https://codeforces.com/profile/{args.username}",',
            '}',
        ]))

    add("npm", _pub("npm",
        "https://registry.npmjs.org/-/user/org.couchdb.user:{args.username}",
        "https://www.npmjs.com/~{args.username}",
        [
            'if "error" in data: raise RuntimeError(data["error"])',
            'result = {',
            '    "site": "npm",',
            '    "username": data.get("name"),',
            '    "email": data.get("email"),',
            '    "profile_url": f"https://www.npmjs.com/~{args.username}",',
            '}',
        ]))

    # Mastodon instances - public lookup API
    for slug, instance, display in [
        ("mastodon_social", "mastodon.social", "Mastodon Social"),
        ("mastodon_cloud", "mastodon.cloud", "Mastodon Cloud"),
        ("mamot", "mamot.fr", "Mamot"),
    ]:
        add(slug, _pub(display,
            f"https://{instance}/api/v1/accounts/lookup?acct={{args.username}}",
            f"https://{instance}/@{{args.username}}",
            [
                'if "error" in data: raise RuntimeError(data.get("error", "Not found."))',
                'result = {',
                f'    "site": "{display}",',
                '    "username": data.get("acct"),',
                '    "display_name": data.get("display_name"),',
                '    "bio": data.get("note"),',
                '    "followers": data.get("followers_count"),',
                '    "following": data.get("following_count"),',
                '    "posts": data.get("statuses_count"),',
                '    "avatar_url": data.get("avatar"),',
                '    "created_at": data.get("created_at"),',
                '    "profile_url": data.get("url"),',
                '}',
            ]))

    add("lemmyworld", _pub("Lemmy World",
        "https://lemmy.world/api/v3/user?username={args.username}",
        "https://lemmy.world/u/{args.username}",
        [
            'u = (data.get("person_view") or {}).get("person") or {}',
            'if not u: raise RuntimeError("User not found.")',
            'agg = (data.get("person_view") or {}).get("counts") or {}',
            'result = {',
            '    "site": "Lemmy World",',
            '    "username": u.get("name"),',
            '    "display_name": u.get("display_name"),',
            '    "bio": u.get("bio"),',
            '    "post_count": agg.get("post_count"),',
            '    "comment_count": agg.get("comment_count"),',
            '    "profile_url": u.get("actor_id"),',
            '}',
        ]))

    add("nitrotype", _pub("NitroType",
        "https://www.nitrotype.com/api/v2/racers/{args.username}",
        "https://www.nitrotype.com/racer/{args.username}",
        [
            'u = (data.get("data") or {}).get("racer") or {}',
            'if not u: raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "NitroType",',
            '    "username": u.get("username"),',
            '    "display_name": u.get("displayName"),',
            '    "tag": u.get("tag"),',
            '    "avg_speed": u.get("avgSpeed"),',
            '    "races_played": u.get("racesPlayed"),',
            '    "profile_url": f"https://www.nitrotype.com/racer/{args.username}",',
            '}',
        ]))

    add("atcoder", _pub("AtCoder",
        "https://atcoder.jp/users/{args.username}/history/json",
        "https://atcoder.jp/users/{args.username}",
        [
            'contests = data if isinstance(data, list) else []',
            'result = {',
            '    "site": "AtCoder",',
            '    "username": args.username,',
            '    "contests_participated": len(contests),',
            '    "last_contest": contests[-1].get("ContestName") if contests else None,',
            '    "last_rating": contests[-1].get("NewRating") if contests else None,',
            '    "profile_url": f"https://atcoder.jp/users/{args.username}",',
            '}',
        ]))

    add("omg_lol", _pub("omg.lol",
        "https://api.omg.lol/address/{args.username}/info",
        "https://omg.lol/{args.username}",
        [
            'if data.get("request", {}).get("status_code") != 200:',
            '    raise RuntimeError("Address not found.")',
            'info = (data.get("response") or {}).get("address") or {}',
            'result = {',
            '    "site": "omg.lol",',
            '    "username": info.get("address"),',
            '    "message": info.get("message"),',
            '    "profile_url": f"https://omg.lol/{args.username}",',
            '}',
        ]))

    add("wattpad", _pub("Wattpad",
        "https://www.wattpad.com/api/v3/users/{args.username}?fields=username,name,description,avatar,numStoriesPublished,numFollowers,numFollowing,createDate",
        "https://www.wattpad.com/user/{args.username}",
        [
            'if "code" in data and data["code"] != 200: raise RuntimeError(data.get("message", "Not found."))',
            'result = {',
            '    "site": "Wattpad",',
            '    "username": data.get("username"),',
            '    "name": data.get("name"),',
            '    "bio": data.get("description"),',
            '    "avatar_url": data.get("avatar"),',
            '    "stories": data.get("numStoriesPublished"),',
            '    "followers": data.get("numFollowers"),',
            '    "following": data.get("numFollowing"),',
            '    "joined": data.get("createDate"),',
            '    "profile_url": f"https://www.wattpad.com/user/{args.username}",',
            '}',
        ]))

    add("itch", _pub("Itch.io",
        "https://itch.io/api/1/x/whoami",  # placeholder — itch has no public user API
        "https://itch.io/profile/{args.username}",
        [
            '# Itch.io has no public user profile API — falls back to HTML scraping.',
            'from common import fetch_text',
            'import re as _re',
            'html = fetch_text(f"https://{args.username}.itch.io", headers={"User-Agent": "Mozilla/5.0"}, timeout=args.timeout)',
            'title_m = _re.search(r"<title[^>]*>([^<]+)</title>", html, _re.I)',
            'desc_m = _re.search(r\'<meta[^>]+name=["\\\']description["\\\'][^>]+content=["\\\']([^"\\\']+)\', html, _re.I)',
            'result = {',
            '    "site": "Itch.io",',
            '    "username": args.username,',
            '    "title": title_m.group(1).strip() if title_m else None,',
            '    "description": desc_m.group(1).strip() if desc_m else None,',
            '    "profile_url": f"https://{args.username}.itch.io",',
            '}',
        ]))

    add("hive_blog", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Hive Blog (blockchain social network).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport json as _json\nimport sys\nfrom pathlib import Path\nfrom urllib.request import Request, urlopen\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import print_json\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Hive Blog user info by username.\")\n    parser.add_argument(\"username\", help=\"Hive Blog username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    try:\n        payload = _json.dumps({\"jsonrpc\": \"2.0\", \"method\": \"condenser_api.get_accounts\", \"params\": [[args.username]], \"id\": 1}).encode()\n        req = Request(\"https://api.hive.blog\", data=payload, headers={\"Content-Type\": \"application/json\", \"User-Agent\": \"site-user-info-scripts/1.0\"})\n        with urlopen(req, timeout=args.timeout) as r:\n            data = _json.loads(r.read().decode())\n        accounts = data.get(\"result\") or []\n        if not accounts:\n            raise RuntimeError(\"User not found.\")\n        u = accounts[0]\n        meta = _json.loads(u.get(\"json_metadata\") or \"{}\").get(\"profile\", {})\n        result = {\n            \"site\": \"Hive Blog\",\n            \"username\": u.get(\"name\"),\n            \"display_name\": meta.get(\"name\"),\n            \"bio\": meta.get(\"about\"),\n            \"location\": meta.get(\"location\"),\n            \"website\": meta.get(\"website\"),\n            \"followers\": u.get(\"follower_count\"),\n            \"following\": u.get(\"following_count\"),\n            \"post_count\": u.get(\"post_count\"),\n            \"created\": u.get(\"created\"),\n            \"profile_url\": f\"https://peakd.com/@{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("wikipedia", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Wikipedia.\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport sys\nfrom pathlib import Path\nfrom urllib.parse import quote\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Wikipedia user info by username.\")\n    parser.add_argument(\"username\", help=\"Wikipedia username\")\n    parser.add_argument(\"--lang\", default=\"en\", help=\"Wiki language code\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    try:\n        url = f\"https://{args.lang}.wikipedia.org/api/rest_v1/page/summary/User:{quote(args.username)}\"\n        data = fetch_json(url, timeout=args.timeout)\n        result = {\n            \"site\": \"Wikipedia\",\n            \"username\": args.username,\n            \"page_title\": data.get(\"title\"),\n            \"extract\": data.get(\"extract\"),\n            \"edit_count\": None,\n            \"profile_url\": f\"https://{args.lang}.wikipedia.org/wiki/User:{quote(args.username)}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    # GraphQL sites
    add("anilist", _graphql("AniList",
        "https://graphql.anilist.co",
        """
query ($username: String) {
  User(name: $username) {
    name siteUrl
    about
    avatar { large }
    statistics { anime { count meanScore } manga { count } }
    followers { pageInfo { total } }
    following { pageInfo { total } }
  }
}""",
        "https://anilist.co/user/{args.username}",
        [
            'u = (data.get("data") or {}).get("User") or {}',
            'if not u: raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "AniList",',
            '    "username": u.get("name"),',
            '    "bio": u.get("about"),',
            '    "avatar_url": (u.get("avatar") or {}).get("large"),',
            '    "anime_count": (u.get("statistics") or {}).get("anime", {}).get("count"),',
            '    "anime_mean_score": (u.get("statistics") or {}).get("anime", {}).get("meanScore"),',
            '    "manga_count": (u.get("statistics") or {}).get("manga", {}).get("count"),',
            '    "profile_url": u.get("siteUrl"),',
            '}',
        ]))

    add("leetcode", _graphql("LeetCode",
        "https://leetcode.com/graphql",
        """
query ($username: String!) {
  matchedUser(username: $username) {
    username
    profile { realName countryName company school ranking }
    submitStats { acSubmissionNum { difficulty count } }
  }
}""",
        "https://leetcode.com/{args.username}/",
        [
            'u = (data.get("data") or {}).get("matchedUser") or {}',
            'if not u: raise RuntimeError("User not found.")',
            'prof = u.get("profile") or {}',
            'result = {',
            '    "site": "LeetCode",',
            '    "username": u.get("username"),',
            '    "name": prof.get("realName"),',
            '    "country": prof.get("countryName"),',
            '    "company": prof.get("company"),',
            '    "school": prof.get("school"),',
            '    "ranking": prof.get("ranking"),',
            '    "solved": sum(s.get("count", 0) for s in (u.get("submitStats") or {}).get("acSubmissionNum", [])),',
            '    "profile_url": f"https://leetcode.com/{args.username}/",',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # API key required
    # -----------------------------------------------------------------------

    add("lastfm", _apikey("Last.fm",
        "https://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={args.username}&api_key={key}&format=json",
        "https://www.last.fm/user/{args.username}",
        "LASTFM_API_KEY",
        ("Authorization", ""),  # not header based — key in URL
        [
            '# Note: auth is via key in URL, not header',
            '# Re-fetch with correct URL',
            'from common import fetch_json as _fj',
            'data = _fj(f"https://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={args.username}&api_key={key}&format=json", timeout=args.timeout)',
            'if "error" in data: raise RuntimeError(data.get("message", "Not found."))',
            'u = data.get("user") or {}',
            'result = {',
            '    "site": "Last.fm",',
            '    "username": u.get("name"),',
            '    "real_name": u.get("realname"),',
            '    "country": u.get("country"),',
            '    "age": u.get("age"),',
            '    "scrobbles": u.get("playcount"),',
            '    "registered": (u.get("registered") or {}).get("#text"),',
            '    "profile_url": u.get("url"),',
            '}',
        ]))

    # Better lastfm implementation without the key-in-url hack
    add("lastfm", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Last.fm (requires LASTFM_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\nfrom urllib.parse import quote\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Last.fm user info by username.\")\n    parser.add_argument(\"username\", help=\"Last.fm username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"LASTFM_API_KEY\", \"\")\n    if not key:\n        print(\"Error: LASTFM_API_KEY not set. Get one at https://www.last.fm/api/account/create\", file=sys.stderr)\n        return 1\n    try:\n        url = f\"https://ws.audioscrobbler.com/2.0/?method=user.getinfo&user={quote(args.username)}&api_key={key}&format=json\"\n        data = fetch_json(url, timeout=args.timeout)\n        if \"error\" in data:\n            raise RuntimeError(data.get(\"message\", \"Not found.\"))\n        u = data.get(\"user\") or {}\n        result = {\n            \"site\": \"Last.fm\",\n            \"username\": u.get(\"name\"),\n            \"real_name\": u.get(\"realname\"),\n            \"country\": u.get(\"country\"),\n            \"scrobbles\": u.get(\"playcount\"),\n            \"registered\": (u.get(\"registered\") or {}).get(\"#text\"),\n            \"profile_url\": u.get(\"url\"),\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("imgur", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Imgur (requires IMGUR_CLIENT_ID).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Imgur user info by username.\")\n    parser.add_argument(\"username\", help=\"Imgur username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    client_id = os.environ.get(\"IMGUR_CLIENT_ID\", \"\")\n    if not client_id:\n        print(\"Error: IMGUR_CLIENT_ID not set. Get one at https://api.imgur.com/oauth2/addclient\", file=sys.stderr)\n        return 1\n    try:\n        data = fetch_json(f\"https://api.imgur.com/3/account/{args.username}\", headers={\"Authorization\": f\"Client-ID {client_id}\"}, timeout=args.timeout)\n        if not data.get(\"success\"): raise RuntimeError(data.get(\"data\", {}).get(\"error\", \"Not found.\"))\n        u = data.get(\"data\") or {}\n        result = {\n            \"site\": \"Imgur\",\n            \"username\": u.get(\"url\"),\n            \"bio\": u.get(\"bio\"),\n            \"reputation\": u.get(\"reputation\"),\n            \"created_at\": u.get(\"created\"),\n            \"profile_url\": f\"https://imgur.com/user/{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("flickr", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Flickr (requires FLICKR_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\nfrom urllib.parse import quote\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Flickr user info by username.\")\n    parser.add_argument(\"username\", help=\"Flickr username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"FLICKR_API_KEY\", \"\")\n    if not key:\n        print(\"Error: FLICKR_API_KEY not set. Get one at https://www.flickr.com/services/api/keys/\", file=sys.stderr)\n        return 1\n    try:\n        base = \"https://api.flickr.com/services/rest/?format=json&nojsoncallback=1\"\n        lookup = fetch_json(f\"{base}&method=flickr.people.findByUsername&username={quote(args.username)}&api_key={key}\", timeout=args.timeout)\n        if lookup.get(\"stat\") != \"ok\": raise RuntimeError(lookup.get(\"message\", \"Not found.\"))\n        nsid = lookup[\"user\"][\"nsid\"]\n        info = fetch_json(f\"{base}&method=flickr.people.getInfo&user_id={nsid}&api_key={key}\", timeout=args.timeout)\n        p = info.get(\"person\") or {}\n        result = {\n            \"site\": \"Flickr\",\n            \"username\": (p.get(\"username\") or {}).get(\"_content\"),\n            \"real_name\": (p.get(\"realname\") or {}).get(\"_content\"),\n            \"location\": (p.get(\"location\") or {}).get(\"_content\"),\n            \"photos\": (p.get(\"photos\") or {}).get(\"count\", {}).get(\"_content\"),\n            \"profile_url\": (p.get(\"profileurl\") or {}).get(\"_content\"),\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("twitch", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Twitch (requires TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\nfrom urllib.parse import urlencode\nfrom urllib.request import Request, urlopen\nimport json as _json\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef _get_token(client_id: str, client_secret: str) -> str:\n    payload = urlencode({\"client_id\": client_id, \"client_secret\": client_secret, \"grant_type\": \"client_credentials\"}).encode()\n    req = Request(\"https://id.twitch.tv/oauth2/token\", data=payload)\n    with urlopen(req, timeout=15) as r:\n        return _json.loads(r.read())[\"access_token\"]\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Twitch user info by username.\")\n    parser.add_argument(\"username\", help=\"Twitch login name\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    client_id = os.environ.get(\"TWITCH_CLIENT_ID\", \"\")\n    client_secret = os.environ.get(\"TWITCH_CLIENT_SECRET\", \"\")\n    if not client_id or not client_secret:\n        print(\"Error: Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET. Register at https://dev.twitch.tv/console\", file=sys.stderr)\n        return 1\n    try:\n        token = _get_token(client_id, client_secret)\n        data = fetch_json(f\"https://api.twitch.tv/helix/users?login={args.username}\", headers={\"Client-Id\": client_id, \"Authorization\": f\"Bearer {token}\"}, timeout=args.timeout)\n        users = data.get(\"data\") or []\n        if not users: raise RuntimeError(\"User not found.\")\n        u = users[0]\n        result = {\n            \"site\": \"Twitch\",\n            \"username\": u.get(\"login\"),\n            \"display_name\": u.get(\"display_name\"),\n            \"bio\": u.get(\"description\"),\n            \"view_count\": u.get(\"view_count\"),\n            \"account_type\": u.get(\"broadcaster_type\"),\n            \"created_at\": u.get(\"created_at\"),\n            \"profile_image_url\": u.get(\"profile_image_url\"),\n            \"profile_url\": f\"https://www.twitch.tv/{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("steam", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Steam (requires STEAM_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef _resolve_vanity(vanity: str, key: str, timeout: int) -> str:\n    data = fetch_json(f\"https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/?vanityurl={vanity}&key={key}\", timeout=timeout)\n    r = data.get(\"response\") or {}\n    if r.get(\"success\") != 1: raise RuntimeError(\"Vanity URL not found.\")\n    return r[\"steamid\"]\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Steam user info by vanity URL.\")\n    parser.add_argument(\"username\", help=\"Steam vanity URL (custom URL)\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"STEAM_API_KEY\", \"\")\n    if not key:\n        print(\"Error: STEAM_API_KEY not set. Get one at https://steamcommunity.com/dev/apikey\", file=sys.stderr)\n        return 1\n    try:\n        steam_id = _resolve_vanity(args.username, key, args.timeout)\n        data = fetch_json(f\"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?steamids={steam_id}&key={key}\", timeout=args.timeout)\n        players = (data.get(\"response\") or {}).get(\"players\") or []\n        if not players: raise RuntimeError(\"User not found.\")\n        p = players[0]\n        result = {\n            \"site\": \"Steam\",\n            \"steam_id\": p.get(\"steamid\"),\n            \"username\": p.get(\"personaname\"),\n            \"real_name\": p.get(\"realname\"),\n            \"country\": p.get(\"loccountrycode\"),\n            \"avatar_url\": p.get(\"avatarfull\"),\n            \"created\": p.get(\"timecreated\"),\n            \"profile_url\": p.get(\"profileurl\"),\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("virustotal", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from VirusTotal (requires VIRUSTOTAL_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get VirusTotal user info.\")\n    parser.add_argument(\"username\", help=\"VirusTotal username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"VIRUSTOTAL_API_KEY\", \"\")\n    if not key:\n        print(\"Error: VIRUSTOTAL_API_KEY not set. Get one at https://www.virustotal.com/gui/join-us\", file=sys.stderr)\n        return 1\n    try:\n        data = fetch_json(f\"https://www.virustotal.com/api/v3/users/{args.username}\", headers={\"x-apikey\": key}, timeout=args.timeout)\n        attrs = (data.get(\"data\") or {}).get(\"attributes\") or {}\n        result = {\n            \"site\": \"VirusTotal\",\n            \"username\": attrs.get(\"name\"),\n            \"email\": attrs.get(\"email\"),\n            \"status\": attrs.get(\"status\"),\n            \"profile_url\": f\"https://www.virustotal.com/gui/user/{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("trakt", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Trakt (requires TRAKT_CLIENT_ID).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Trakt user info by username.\")\n    parser.add_argument(\"username\", help=\"Trakt username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    client_id = os.environ.get(\"TRAKT_CLIENT_ID\", \"\")\n    if not client_id:\n        print(\"Error: TRAKT_CLIENT_ID not set. Get one at https://trakt.tv/oauth/applications\", file=sys.stderr)\n        return 1\n    try:\n        data = fetch_json(f\"https://api.trakt.tv/users/{args.username}\", headers={\"trakt-api-key\": client_id, \"trakt-api-version\": \"2\"}, timeout=args.timeout)\n        stats = fetch_json(f\"https://api.trakt.tv/users/{args.username}/stats\", headers={\"trakt-api-key\": client_id, \"trakt-api-version\": \"2\"}, timeout=args.timeout)\n        result = {\n            \"site\": \"Trakt\",\n            \"username\": data.get(\"username\"),\n            \"name\": data.get(\"name\"),\n            \"bio\": data.get(\"about\"),\n            \"location\": data.get(\"location\"),\n            \"movies_watched\": (stats.get(\"movies\") or {}).get(\"watched\"),\n            \"shows_watched\": (stats.get(\"shows\") or {}).get(\"watched\"),\n            \"profile_url\": f\"https://trakt.tv/users/{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    add("genius", "#!/usr/bin/env python3\n\"\"\"Fetch user profile information from Genius (requires GENIUS_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\nfrom urllib.parse import quote\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Genius user info by username.\")\n    parser.add_argument(\"username\", help=\"Genius username\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"GENIUS_API_KEY\", \"\")\n    if not key:\n        print(\"Error: GENIUS_API_KEY not set. Get one at https://genius.com/api-clients\", file=sys.stderr)\n        return 1\n    try:\n        search = fetch_json(f\"https://api.genius.com/search?q={quote(args.username)}\", headers={\"Authorization\": f\"Bearer {key}\"}, timeout=args.timeout)\n        # Search for user by name in users endpoint\n        data = fetch_json(f\"https://api.genius.com/users/{quote(args.username)}\", headers={\"Authorization\": f\"Bearer {key}\"}, timeout=args.timeout)\n        u = (data.get(\"response\") or {}).get(\"user\") or {}\n        result = {\n            \"site\": \"Genius\",\n            \"username\": u.get(\"login\"),\n            \"name\": u.get(\"name\"),\n            \"bio\": (u.get(\"about_me\") or {}).get(\"plain\"),\n            \"followers\": u.get(\"followers_count\"),\n            \"iq\": u.get(\"iq\"),\n            \"profile_url\": u.get(\"url\"),\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    # -----------------------------------------------------------------------
    # HTML scrapers
    # -----------------------------------------------------------------------

    for slug, name, url in [
        ("letterboxd", "Letterboxd", "https://letterboxd.com/{args.username}/"),
        ("goodreads", "GoodReads", "https://www.goodreads.com/{args.username}"),
        ("myanimelist", "MyAnimeList", "https://myanimelist.net/profile/{args.username}"),
        ("grailed", "Grailed", "https://www.grailed.com/{args.username}"),
        ("houzz", "Houzz", "https://www.houzz.com/user/{args.username}"),
        ("archive_of_our_own", "Archive of Our Own", "https://archiveofourown.org/users/{args.username}"),
        ("star_citizen", "Star Citizen", "https://robertsspaceindustries.com/citizens/{args.username}"),
        ("ultimate_guitar", "Ultimate Guitar", "https://www.ultimate-guitar.com/u/{args.username}"),
        ("redbubble", "Redbubble", "https://www.redbubble.com/people/{args.username}/shop"),
        ("kongregate", "Kongregate", "https://www.kongregate.com/accounts/{args.username}"),
        ("reverbnation", "ReverbNation", "https://www.reverbnation.com/{args.username}"),
        ("gumroad", "Gumroad", "https://gumroad.com/{args.username}"),
        ("kofi", "Ko-fi", "https://ko-fi.com/{args.username}"),
        ("buymeacoffee", "BuyMeACoffee", "https://www.buymeacoffee.com/{args.username}"),
        ("speakerdeck", "SpeakerDeck", "https://speakerdeck.com/{args.username}"),
        ("myminifactory", "MyMiniFactory", "https://www.myminifactory.com/users/{args.username}"),
        ("hackmd", "HackMD", "https://hackmd.io/@{args.username}"),
        ("about_me", "About.me", "https://about.me/{args.username}"),
        ("bugcrowd", "Bugcrowd", "https://bugcrowd.com/{args.username}"),
        ("hackerone", "HackerOne", "https://hackerone.com/{args.username}"),
        ("codepen", "Codepen", "https://codepen.io/{args.username}"),
        ("linktree", "Linktree", "https://linktr.ee/{args.username}"),
        ("psn_profiles", "PSNProfiles", "https://psnprofiles.com/{args.username}"),
        ("allMyLinks", "AllMyLinks", "https://allmylinks.com/{args.username}"),
        ("wikidot", "Wikidot", "https://www.wikidot.com/user:info/{args.username}"),
        ("livejournal", "LiveJournal", "https://www.livejournal.com/profile?user={args.username}"),
        ("academia", "Academia.edu", "https://www.academia.edu/{args.username}"),
        ("curseforge", "CurseForge", "https://www.curseforge.com/members/{args.username}"),
        ("pinkbike", "Pinkbike", "https://www.pinkbike.com/u/{args.username}/"),
        ("geocaching", "Geocaching", "https://www.geocaching.com/p/?u={args.username}"),
        ("typeracer", "Typeracer", "https://data.typeracer.com/pit/profile?user={args.username}"),
        ("coderwall", "Coderwall", "https://coderwall.com/{args.username}"),
        ("codersrank", "Coders Rank", "https://profile.codersrank.io/user/{args.username}"),
        ("dribbble", "Dribbble", "https://dribbble.com/{args.username}"),
        ("behance", "Behance", "https://www.behance.net/{args.username}"),
        ("flickr", "Flickr", "https://www.flickr.com/photos/{args.username}"),
        ("write_as", "Write.as", "https://write.as/{args.username}/"),
        ("habr", "Habr", "https://habr.com/en/users/{args.username}/"),
        ("pikabu", "Pikabu", "https://pikabu.ru/@{args.username}"),
        ("coroflot", "Coroflot", "https://www.coroflot.com/{args.username}"),
        ("hackster", "Hackster", "https://www.hackster.io/{args.username}"),
        ("vjudge", "Vjudge", "https://vjudge.net/user/{args.username}"),
        ("codechef", "CodeChef", "https://www.codechef.com/users/{args.username}"),
        ("hackerearth", "HackerEarth", "https://www.hackerearth.com/@{args.username}/"),
        ("launchpad", "Launchpad", "https://launchpad.net/~{args.username}"),
        ("odysee", "Odysee", "https://odysee.com/@{args.username}"),
        ("crowdin", "Crowdin", "https://crowdin.com/{args.username}"),
        ("polarsteps", "Polarsteps", "https://www.polarsteps.com/{args.username}"),
        ("gaiaonline", "GaiaOnline", "https://www.gaiaonline.com/profiles/{args.username}/"),
        ("tellonym", "Tellonym", "https://tellonym.me/{args.username}"),
        ("memrise", "Memrise", "https://app.memrise.com/user/{args.username}/"),
        ("flipboard", "Flipboard", "https://flipboard.com/@{args.username}"),
        ("codecademy", "Codecademy", "https://www.codecademy.com/profiles/{args.username}"),
        ("replit", "Replit", "https://replit.com/@{args.username}"),
        ("wordpress", "WordPress", "https://{args.username}.wordpress.com"),
        ("scratch", "Scratch", "https://scratch.mit.edu/users/{args.username}/"),
        ("wowhead", "Wowhead", "https://www.wowhead.com/user={args.username}"),
        ("gamespot", "GameFAQs", "https://gamefaqs.gamespot.com/community/{args.username}"),
        ("nairaland", "Nairaland", "https://www.nairaland.com/{args.username}"),
        ("weebly", "Weebly", "https://{args.username}.weebly.com"),
        ("drive2", "Drive2", "https://www.drive2.ru/users/{args.username}"),
        ("fixya", "Fixya", "https://www.fixya.com/users/{args.username}"),
        ("furaffinity", "FurAffinity", "https://www.furaffinity.net/user/{args.username}/"),
        ("codesandbox", "CodeSandbox", "https://codesandbox.io/u/{args.username}"),
        ("colourlovers", "ColourLovers", "https://www.colourlovers.com/lover/{args.username}"),
        ("bookcrossing", "Bookcrossing", "https://www.bookcrossing.com/mybookshelf/{args.username}"),
        ("peppernl", "PepperNL", "https://www.pepper.nl/profile/{args.username}"),
        ("pepperpl", "PepperPL", "https://www.pepper.pl/profile/{args.username}"),
        ("mydealz", "Mydealz", "https://www.mydealz.de/profile/{args.username}"),
        ("dealabs", "Dealabs", "https://www.dealabs.com/profile/{args.username}"),
        ("chollometro", "Chollometro", "https://www.chollometro.com/profile/{args.username}"),
        ("promodescuentos", "Promodescuentos", "https://www.promodescuentos.com/profile/{args.username}"),
        ("wykop", "Wykop", "https://www.wykop.pl/ludzie/{args.username}/"),
        ("kaskus", "Kaskus", "https://www.kaskus.co.id/@{args.username}"),
        ("vjudge", "Vjudge", "https://vjudge.net/user/{args.username}"),
        ("mydramalist", "MyDramaList", "https://mydramalist.com/profile/{args.username}"),
        ("gitbook", "GitBook", "https://app.gitbook.com/@{args.username}/"),
        ("hackmd", "HackMD", "https://hackmd.io/@{args.username}"),
        ("tistory", "Tistory", "https://{args.username}.tistory.com"),
        ("naver", "Naver", "https://blog.naver.com/{args.username}"),
        ("plurk", "Plurk", "https://www.plurk.com/{args.username}"),
        ("igromania", "Igromania", "https://forums.igromania.ru/member.php?username={args.username}"),
        ("championat", "Championat", "https://www.championat.com/user/{args.username}/"),
        ("habr", "Habr", "https://habr.com/en/users/{args.username}/"),
        ("linuxfr", "LinuxFR.org", "https://linuxfr.org/users/{args.username}"),
        ("jeuxvideo", "Jeuxvideo", "https://www.jeuxvideo.com/profil/{args.username}"),
        ("swapd", "SWAPD", "https://swapd.co/{args.username}"),
        ("clapper", "Clapper", "https://clapperapp.com/{args.username}"),
        ("kwork", "Kwork", "https://kwork.ru/user/{args.username}"),
        ("soop", "SOOP", "https://www.sooplive.com/{args.username}"),
        ("couchsurfing", "Couchsurfing", "https://www.couchsurfing.com/people/{args.username}"),
        ("blitztactics", "Blitz Tactics", "https://blitztactics.com/users/{args.username}"),
        ("vlr", "VLR", "https://www.vlr.gg/player/{args.username}"),
        ("d3ru", "D3.ru", "https://d3.ru/user/{args.username}/"),
        ("datingru", "DatingRU", "https://www.mamba.ru/user{args.username}"),
        ("rajce", "Rajce.net", "https://www.rajce.idnes.cz/{args.username}/"),
        ("akniga", "Akniga", "https://akniga.org/profile/{args.username}"),
        ("buzzfeed", "BuzzFeed", "https://www.buzzfeed.com/{args.username}"),
        ("tuna", "Tuna", "https://tuna.am/{args.username}"),
        ("note_jp", "Note.com", "https://note.com/{args.username}"),
        ("tiendanube", "Tiendanube", "https://www.tiendanube.com/{args.username}"),
        ("packagist", "Packagist", "https://packagist.org/users/{args.username}/"),
        ("sublimeforum", "SublimeForum", "https://forum.sublimetext.com/u/{args.username}"),
        ("gutefrage", "Gutefrage", "https://www.gutefrage.net/nutzer/{args.username}"),
        ("dcinside", "DCinside", "https://gallog.dcinside.com/{args.username}"),
        ("cartalkcommunity", "Car Talk Community", "https://community.cartalk.com/u/{args.username}"),
        ("nintendolife", "Nintendo Life", "https://www.nintendolife.com/users/{args.username}"),
        ("warrior_forum", "Warrior Forum", "https://www.warriorforum.com/members/{args.username}.html"),
        ("youknowmeme", "Wowhead", "https://www.wowhead.com/user={args.username}"),
    ]:
        if slug not in sites:
            sites[slug] = _html(name, url)

    # -----------------------------------------------------------------------
    # Playwright-required (JS-rendered or heavily anti-bot)
    # -----------------------------------------------------------------------

    for slug, name, reason in [
        ("youtube", "YouTube", "YouTube profiles are JS-rendered. Use Playwright with a logged-in session cookie (YOUTUBE_COOKIE) or the YouTube Data API v3 (YOUTUBE_API_KEY)."),
        ("tiktok", "TikTok", "TikTok aggressively blocks automated requests. Requires Playwright with a valid session cookie (TIKTOK_SESSION_ID) or the unofficial mobile API."),
        ("vsco", "VSCO", "VSCO requires JavaScript rendering. Use Playwright; even then Cloudflare may block headless browsers."),
        ("threads", "Threads", "Threads (Meta) requires login and renders via JS. No public API exists."),
        ("snapchat", "Snapchat", "Snapchat blocks all automated requests. The public profile page requires JS and often triggers CAPTCHA."),
        ("pinterest", "Pinterest", "Pinterest requires login for most profile data and renders profiles via JS."),
        ("patreon", "Patreon", "Patreon renders profiles via JS and requires OAuth for API access."),
        ("venmo", "Venmo", "Venmo profiles are JS-rendered SPAs. No public API; requires Playwright with session cookie (VENMO_COOKIE)."),
        ("strava", "Strava", "Strava requires OAuth 2.0 authentication. No public profile scraping without STRAVA_ACCESS_TOKEN."),
        ("instagram", "Instagram", "Instagram blocks all automated requests and requires login."),
        ("facebook", "Facebook", "Facebook blocks all automated requests and requires login."),
        ("clubhouse", "Clubhouse", "Clubhouse has no public user profile pages or API without authentication."),
        ("slack", "Slack", "Slack has no public user profile pages; all profiles require workspace membership."),
        ("soundcloud", "SoundCloud", "SoundCloud requires a client_id (obtained from inspecting network requests) which changes frequently."),
        ("telegram", "Telegram", "Telegram has no public profile lookup by username without the Telegram Bot API (requires bot token and the user to have messaged your bot)."),
        ("tumblr", "Tumblr", "Tumblr's v2 API requires OAuth. HTML fallback works but rate-limits quickly."),
        ("kick", "Kick", "Kick's API requires authentication. Public HTML is JS-rendered."),
        ("disqus", "Disqus", "Disqus requires DISQUS_API_KEY and DISQUS_API_SECRET. Register at https://disqus.com/api/applications/"),
        ("osu", "osu!", "osu! requires OSU_API_KEY from https://osu.ppy.sh/home/account/edit. Set OSU_API_KEY in .env."),
        ("vimeo", "Vimeo", "Vimeo requires a VIMEO_ACCESS_TOKEN from https://developer.vimeo.com/apps. The public API is limited without auth."),
        ("trello", "Trello", "Trello requires TRELLO_API_KEY and TRELLO_TOKEN from https://trello.com/app-key. User profiles are not public."),
        ("freelancer", "Freelancer", "Freelancer requires FREELANCER_OAUTH_TOKEN for its API. HTML profiles are JS-rendered."),
        ("tenor", "Tenor", "Tenor (Google) has GIF search but no public user profile concept by username."),
        ("blogger", "Blogger", "Blogger profiles are identified by numeric IDs, not usernames. Custom domain blogs can be scraped but mapping username → blog ID requires Google search."),
        ("geocaching", "Geocaching", "Geocaching profiles require login. The public page redirects to login for non-members."),
        ("myanimelist", "MyAnimeList", "MyAnimeList's official API v2 requires a client ID (MYANIMELIST_CLIENT_ID). HTML scraping is blocked by Cloudflare."),
        ("furaffinity", "FurAffinity", "FurAffinity requires a logged-in session cookie (FA_COOKIE_A and FA_COOKIE_B) for most profile pages."),
        ("untappd", "Untappd", "Untappd requires UNTAPPD_CLIENT_ID and UNTAPPD_CLIENT_SECRET for API access."),
        ("weebly", "Weebly", "Weebly custom domains vary per user; {username}.weebly.com is not guaranteed. No user search API."),
        ("tumblr", "Tumblr", "Tumblr API v2 requires OAuth. HTML fallback: {username}.tumblr.com but rate-limits quickly."),
        ("vk", "VK", "VK (VKontakte) requires VK_ACCESS_TOKEN for API access. Register at https://vk.com/apps?act=manage."),
        ("gravatar", "Gravatar", "Gravatar profiles are keyed by email MD5 hash, not username. Without the email address, username lookup is not possible."),
        ("flightradar24", "Flightradar24", "Flightradar24 is a flight tracking service — it has no user profile concept accessible by username."),
        ("nintendo_life", "NintendoLife", "NintendoLife is a gaming news site — it has no public user profiles by username."),
        ("soop", "SOOP", "SOOP (Korean streaming) requires login and KR localization; automated access is blocked."),
        ("bluesky", "Bluesky", ""),  # already added as public_api above — skip
        ("couchsurfing", "Couchsurfing", "Couchsurfing requires login to view profiles."),
        ("datingru", "DatingRU (Mamba)", "Mamba requires login and serves profiles via JS."),
        ("forumofsports", "Forum Guns", "forum_guns.ru profiles require login."),
        ("clapper", "Clapper", "Clapper profiles are JS-rendered and require login."),
        ("empretienda", "Empretienda AR", "Empretienda Argentina — store pages vary per merchant; no unified username lookup."),
        ("womansday", "Kvinneguiden", "Kvinneguiden (Norwegian forum) requires login to view profiles."),
    ]:
        if slug not in sites:
            sites[slug] = _blocked(name, reason)

    # -----------------------------------------------------------------------
    # HudsonRock — public breach check API
    # -----------------------------------------------------------------------
    add("hudsonrock", _pub("HudsonRock",
        "https://cavalier.hudsonrock.com/api/json/v2/osint-tools/is-user-compromised?username={args.username}",
        "https://cavalier.hudsonrock.com/api/json/v2/osint-tools/is-user-compromised?username={args.username}",
        [
            'result = {',
            '    "site": "HudsonRock",',
            '    "username": args.username,',
            '    "compromised": data.get("have_it"),',
            '    "stealers": data.get("stealers"),',
            '    "total_credentials": data.get("total_credentials"),',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # Memrise — semi-public API
    # -----------------------------------------------------------------------
    add("memrise", _pub("Memrise",
        "https://app.memrise.com/api/1/user/?username={args.username}",
        "https://app.memrise.com/user/{args.username}/",
        [
            'users = (data.get("users") or {}).get("results") or []',
            'if not users: raise RuntimeError("User not found.")',
            'u = users[0]',
            'result = {',
            '    "site": "Memrise",',
            '    "username": u.get("username"),',
            '    "display_name": u.get("name"),',
            '    "bio": u.get("tagline"),',
            '    "points": u.get("points"),',
            '    "courses": u.get("courses_count"),',
            '    "profile_url": f"https://app.memrise.com/user/{args.username}/",',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # Open Collective — public API
    # -----------------------------------------------------------------------
    add("opencollective", _pub("Open Collective",
        "https://opencollective.com/{args.username}/json",
        "https://opencollective.com/{args.username}",
        [
            'if "error" in data: raise RuntimeError(str(data["error"]))',
            'result = {',
            '    "site": "Open Collective",',
            '    "username": data.get("slug"),',
            '    "name": data.get("name"),',
            '    "description": data.get("description"),',
            '    "location": data.get("location"),',
            '    "website": data.get("website"),',
            '    "twitter": data.get("twitterHandle"),',
            '    "github": data.get("githubHandle"),',
            '    "profile_url": f"https://opencollective.com/{args.username}",',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # Monkeytype — public API
    # -----------------------------------------------------------------------
    add("monkeytype", _pub("Monkeytype",
        "https://api.monkeytype.com/users/{args.username}/profile",
        "https://monkeytype.com/profile/{args.username}",
        [
            'if data.get("message") and "not found" in data.get("message","").lower():',
            '    raise RuntimeError("User not found.")',
            'd = (data.get("data") or {})',
            'result = {',
            '    "site": "Monkeytype",',
            '    "username": d.get("name"),',
            '    "bio": d.get("bio"),',
            '    "keyboard": d.get("keyboard"),',
            '    "twitter": d.get("twitter"),',
            '    "github": d.get("github"),',
            '    "discord": d.get("discord"),',
            '    "profile_url": f"https://monkeytype.com/profile/{args.username}",',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # ProductHunt — GraphQL
    # -----------------------------------------------------------------------
    add("producthunt", _graphql("Product Hunt",
        "https://api.producthunt.com/v2/api/graphql",
        """
query ($username: String!) {
  user(username: $username) {
    name username headline websiteUrl twitterUsername
    followersCount followingCount votesCount
    profileImage
  }
}""",
        "https://www.producthunt.com/@{args.username}",
        [
            'u = (data.get("data") or {}).get("user") or {}',
            'if not u: raise RuntimeError("User not found.")',
            'result = {',
            '    "site": "Product Hunt",',
            '    "username": u.get("username"),',
            '    "name": u.get("name"),',
            '    "headline": u.get("headline"),',
            '    "website": u.get("websiteUrl"),',
            '    "twitter": u.get("twitterUsername"),',
            '    "followers": u.get("followersCount"),',
            '    "following": u.get("followingCount"),',
            '    "votes": u.get("votesCount"),',
            '    "profile_url": f"https://www.producthunt.com/@{args.username}",',
            '}',
        ]))

    # -----------------------------------------------------------------------
    # Pastebin — lookup by username (HTML)
    # -----------------------------------------------------------------------
    add("pastebin_user", _html("Pastebin User",
        "https://pastebin.com/u/{args.username}"))

    # -----------------------------------------------------------------------
    # Codepen, GitHub, etc. covered elsewhere — skip if already in sites
    # -----------------------------------------------------------------------

    # Steam Community Group
    add("steam_group", "#!/usr/bin/env python3\n\"\"\"Fetch Steam Community group info (requires STEAM_API_KEY).\"\"\"\n\nfrom __future__ import annotations\n\nimport argparse\nimport os\nimport sys\nfrom pathlib import Path\n\nROOT_DIR = Path(__file__).resolve().parents[1]\nif str(ROOT_DIR) not in sys.path:\n    sys.path.insert(0, str(ROOT_DIR))\n\nfrom common import fetch_json, print_json, load_env_file\n\nload_env_file()\n\n\ndef main() -> int:\n    parser = argparse.ArgumentParser(description=\"Get Steam Community group info.\")\n    parser.add_argument(\"username\", help=\"Steam group name\")\n    parser.add_argument(\"--timeout\", type=int, default=20)\n    args = parser.parse_args()\n    key = os.environ.get(\"STEAM_API_KEY\", \"\")\n    if not key:\n        print(\"Error: STEAM_API_KEY not set.\", file=sys.stderr)\n        return 1\n    try:\n        data = fetch_json(f\"https://api.steampowered.com/ISteamUser/GetGroupSummary/v1/?groupname={args.username}&key={key}\", timeout=args.timeout)\n        g = (data.get(\"response\") or {}).get(\"group_details\") or {}\n        result = {\n            \"site\": \"Steam Community (Group)\",\n            \"group_name\": g.get(\"group_name\"),\n            \"headline\": g.get(\"headline\"),\n            \"summary\": g.get(\"summary\"),\n            \"member_count\": g.get(\"member_count\"),\n            \"profile_url\": f\"https://steamcommunity.com/groups/{args.username}\",\n        }\n        print_json(result)\n        return 0\n    except Exception as exc:\n        print(f\"Error: {exc}\", file=sys.stderr)\n        return 1\n\n\nif __name__ == \"__main__\":\n    raise SystemExit(main())\n")

    return sites


# ---------------------------------------------------------------------------
# Write files
# ---------------------------------------------------------------------------

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    sites = build_all()
    created = []
    skipped = []
    for slug, code in sites.items():
        path = OUT / f"{slug}_user_info.py"
        path.write_text(code, encoding="utf-8")
        created.append(path.name)

    print(f"Created {len(created)} scraper files in {OUT}")
    for name in sorted(created):
        print(f"  {name}")


if __name__ == "__main__":
    main()
