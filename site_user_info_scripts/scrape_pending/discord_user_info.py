"""
discord_user_info.py
Fetches a Discord user's public profile via the Discord REST API.

Requires: DISCORD_BOT_TOKEN env variable.
  Create a bot at https://discord.com/developers/applications
  No server permissions needed — just the token itself.

Supports lookup by:
  • numeric user ID  (e.g. "80351110224678912")

Note: Discord does NOT support username→ID lookup via public API.
      You must supply the numeric ID. If you only have a username,
      you can find the ID by enabling Developer Mode in Discord and
      right-clicking the user → Copy User ID.

Returns fields:
  id, username, display_name, discriminator, bio, avatar_url,
  banner_url, accent_color, badges[], created_at (derived from snowflake),
  bot, system, public_flags_decoded[]
"""

import sys, os, datetime
from scraper_base import new_session, ok, err, dump

SITE = "discord"
API_BASE = "https://discord.com/api/v10"

# Discord badge flags
FLAGS = {
    1 << 0: "Discord_Staff",
    1 << 1: "Partnered_Server_Owner",
    1 << 2: "HypeSquad_Events",
    1 << 3: "Bug_Hunter_Level_1",
    1 << 6: "HypeSquad_Bravery",
    1 << 7: "HypeSquad_Brilliance",
    1 << 8: "HypeSquad_Balance",
    1 << 9: "Early_Supporter",
    1 << 14: "Bug_Hunter_Level_2",
    1 << 17: "Early_Verified_Bot_Developer",
    1 << 18: "Moderator_Programs_Alumni",
    1 << 22: "Active_Developer",
}


def _snowflake_to_dt(snowflake_id: str) -> str:
    """Convert Discord snowflake ID to ISO timestamp."""
    ts = (int(snowflake_id) >> 22) + 1420070400000
    return datetime.datetime.utcfromtimestamp(ts / 1000).isoformat() + "Z"


def _avatar_url(
    user_id: str, avatar_hash: str | None, ext="png", size=512
) -> str | None:
    if not avatar_hash:
        return None
    fmt = "gif" if avatar_hash.startswith("a_") else ext
    return (
        f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.{fmt}?size={size}"
    )


def _banner_url(user_id: str, banner_hash: str | None) -> str | None:
    if not banner_hash:
        return None
    fmt = "gif" if banner_hash.startswith("a_") else "png"
    return f"https://cdn.discordapp.com/banners/{user_id}/{banner_hash}.{fmt}?size=600"


def scrape(user_id: str, bot_token: str | None = None) -> dict:
    bot_token = bot_token or os.environ.get("DISCORD_BOT_TOKEN")
    if not bot_token:
        return err(
            SITE,
            (
                "DISCORD_BOT_TOKEN not set. "
                "Create a bot at https://discord.com/developers/applications "
                "then export DISCORD_BOT_TOKEN=Bot_your_token_here"
            ),
        )

    s = new_session()
    s.headers.update({"Authorization": f"Bot {bot_token}"})

    # Fetch base user object
    try:
        r = s.get(f"{API_BASE}/users/{user_id}", timeout=10)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 401:
        return err(SITE, "invalid bot token (401)")
    if r.status_code == 404:
        return err(SITE, f"user ID '{user_id}' not found")
    if r.status_code == 429:
        return err(SITE, "rate limited — wait and retry")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}")

    u = r.json()

    # Fetch extended profile (bio, banner) — requires the profile endpoint
    profile = {}
    rp = s.get(f"{API_BASE}/users/{user_id}/profile", timeout=10)
    if rp.status_code == 200:
        profile = rp.json()

    flags = u.get("public_flags", 0)
    badges = [name for bit, name in FLAGS.items() if flags & bit]

    # Global display name (new username system)
    display_name = (
        u.get("global_name")
        or profile.get("user", {}).get("global_name")
        or u.get("username")
    )

    return ok(
        SITE,
        u.get("username"),
        {
            "url": f"https://discord.com/users/{user_id}",
            "id": u.get("id"),
            "username": u.get("username"),
            "display_name": display_name,
            "discriminator": u.get("discriminator"),  # "0" on new system
            "bio": profile.get("user", {}).get("bio") or u.get("bio"),
            "avatar_url": _avatar_url(user_id, u.get("avatar")),
            "banner_url": _banner_url(
                user_id, u.get("banner") or profile.get("user", {}).get("banner")
            ),
            "accent_color": u.get("accent_color"),
            "badges": badges,
            "public_flags": flags,
            "bot": u.get("bot", False),
            "system": u.get("system", False),
            "created_at": _snowflake_to_dt(user_id),
            "premium_type": profile.get("premium_type"),
            "mutual_guilds": len(profile.get("mutual_guilds") or []),
        },
    )


if __name__ == "__main__":
    uid = sys.argv[1] if len(sys.argv) > 1 else "80351110224678912"
    print(dump(scrape(uid)))
