"""
crunchbase_user_info.py
Fetches a Crunchbase person entity via the official v4 API.

Requires: CRUNCHBASE_API_KEY env variable (free tier available at
          https://data.crunchbase.com/docs/using-the-api)

Supports lookup by:
  • Crunchbase permalink slug  (e.g. "elon-musk")

Returns fields:
  name, first_name, last_name, title, location_identifiers[],
  short_description, primary_job_title, primary_organization,
  num_founded_organizations, num_investments, num_exits,
  social_media{}, profile_image_url, rank_person, updated_at
"""

import sys, os
from scraper_base import new_session, ok, err, dump

SITE = "crunchbase"
API_URL = "https://api.crunchbase.com/api/v4/entities/people/{slug}"

FIELDS = ",".join(
    [
        "first_name",
        "last_name",
        "title",
        "short_description",
        "primary_job_title",
        "primary_organization",
        "location_identifiers",
        "num_founded_organizations",
        "num_investments",
        "num_exits",
        "profile_image_url",
        "rank_person",
        "updated_at",
        "twitter",
        "linkedin",
        "facebook",
    ]
)


def scrape(slug: str, api_key: str | None = None) -> dict:
    api_key = api_key or os.environ.get("CRUNCHBASE_API_KEY")
    if not api_key:
        return err(
            SITE,
            (
                "CRUNCHBASE_API_KEY not set. "
                "Get a free key at https://data.crunchbase.com/docs/using-the-api "
                "then export CRUNCHBASE_API_KEY=your_key"
            ),
        )

    s = new_session()
    url = API_URL.format(slug=slug)

    try:
        r = s.get(url, params={"user_key": api_key, "field_ids": FIELDS}, timeout=15)
    except Exception as e:
        return err(SITE, str(e))

    if r.status_code == 401:
        return err(SITE, "invalid API key (401)")
    if r.status_code == 404:
        return err(SITE, f"person slug '{slug}' not found (404)")
    if r.status_code != 200:
        return err(SITE, f"HTTP {r.status_code}: {r.text[:200]}")

    data = r.json()
    props = data.get("properties", {})

    def prop(key):
        v = props.get(key)
        if isinstance(v, dict):
            return v.get("value") or v.get("permalink") or v
        return v

    org = props.get("primary_organization", {})

    return ok(
        SITE,
        slug,
        {
            "url": f"https://www.crunchbase.com/person/{slug}",
            "name": f"{prop('first_name')} {prop('last_name')}".strip(),
            "first_name": prop("first_name"),
            "last_name": prop("last_name"),
            "title": prop("title"),
            "short_description": prop("short_description"),
            "primary_job_title": prop("primary_job_title"),
            "primary_organization": org.get("value") if isinstance(org, dict) else org,
            "location": [
                l.get("value") for l in (props.get("location_identifiers") or [])
            ],
            "num_founded_organizations": prop("num_founded_organizations"),
            "num_investments": prop("num_investments"),
            "num_exits": prop("num_exits"),
            "profile_image_url": prop("profile_image_url"),
            "rank_person": prop("rank_person"),
            "updated_at": prop("updated_at"),
            "social_links": {
                "twitter": prop("twitter"),
                "linkedin": prop("linkedin"),
                "facebook": prop("facebook"),
            },
        },
    )


if __name__ == "__main__":
    slug = sys.argv[1] if len(sys.argv) > 1 else "elon-musk"
    print(dump(scrape(slug)))
