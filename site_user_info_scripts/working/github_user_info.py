#!/usr/bin/env python3
"""Fetch user profile information from GitHub's public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json

NOREPLY_SUFFIX = "@users.noreply.github.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get GitHub user info by username.")
    parser.add_argument("username", help="GitHub username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    parser.add_argument("--no-commits", action="store_true", help="Skip commit email extraction")
    return parser.parse_args()


def _extract_commit_emails(username: str, timeout: int) -> list[str]:
    """Extract email addresses from commit history across owned repos."""
    repos_url = (
        f"https://api.github.com/users/{quote(username)}/repos"
        "?per_page=10&sort=pushed&type=owner"
    )
    try:
        repos = fetch_json(repos_url, timeout=timeout)
    except Exception:
        return []

    emails: set[str] = set()
    for repo in repos:
        if repo.get("fork"):
            continue
        repo_name = repo.get("name", "")
        commits_url = (
            f"https://api.github.com/repos/{quote(username)}/{quote(repo_name)}"
            f"/commits?author={quote(username)}&per_page=5"
        )
        try:
            commits = fetch_json(commits_url, timeout=timeout)
        except Exception:
            continue
        for commit in commits:
            email = (commit.get("commit") or {}).get("author", {}).get("email") or ""
            if email and not email.endswith(NOREPLY_SUFFIX):
                emails.add(email)
        if len(emails) >= 5:
            break

    return sorted(emails)


def _fetch_orgs(username: str, timeout: int) -> list[dict]:
    try:
        orgs = fetch_json(
            f"https://api.github.com/users/{quote(username)}/orgs",
            timeout=timeout,
        )
        return [
            {"login": o.get("login"), "url": f"https://github.com/{o.get('login')}"}
            for o in orgs
        ]
    except Exception:
        return []


def _fetch_top_repos(username: str, timeout: int) -> list[dict]:
    try:
        repos = fetch_json(
            f"https://api.github.com/users/{quote(username)}/repos"
            "?per_page=5&sort=stars&direction=desc&type=owner",
            timeout=timeout,
        )
        return [
            {
                "name": r.get("name"),
                "description": r.get("description"),
                "stars": r.get("stargazers_count"),
                "language": r.get("language"),
                "url": r.get("html_url"),
                "pushed_at": r.get("pushed_at"),
            }
            for r in repos
            if not r.get("fork")
        ][:5]
    except Exception:
        return []


def main() -> int:
    args = parse_args()
    endpoint = f"https://api.github.com/users/{quote(args.username)}"
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        username = data.get("login") or args.username

        commit_emails = (
            [] if args.no_commits
            else _extract_commit_emails(username, args.timeout)
        )
        orgs = _fetch_orgs(username, args.timeout)
        top_repos = _fetch_top_repos(username, args.timeout)

        result = {
            "site": "GitHub",
            "username": username,
            "name": data.get("name"),
            "bio": data.get("bio"),
            "company": data.get("company"),
            "location": data.get("location"),
            "email": data.get("email"),
            "commit_emails": commit_emails,
            "blog": data.get("blog"),
            "public_repos": data.get("public_repos"),
            "followers": data.get("followers"),
            "following": data.get("following"),
            "organizations": orgs,
            "top_repos": top_repos,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "profile_url": data.get("html_url"),
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
