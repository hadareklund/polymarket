#!/usr/bin/env python3
"""Fetch user profile information from Hugging Face."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def main() -> int:
    parser = argparse.ArgumentParser(description="Get Hugging Face user info by username.")
    parser.add_argument("username", help="Hugging Face username")
    parser.add_argument("--timeout", type=int, default=20)
    args = parser.parse_args()
    try:
        data = fetch_json(f"https://huggingface.co/api/users/{args.username}", timeout=args.timeout)
        if "error" in data: raise RuntimeError(data.get("error", "Not found."))
        result = {
            "site": "Hugging Face",
            "username": data.get("name"),
            "full_name": data.get("fullname"),
            "bio": data.get("details"),
            "location": data.get("location"),
            "website": data.get("websiteUrl"),
            "followers": data.get("numFollowers"),
            "models": data.get("numModels"),
            "datasets": data.get("numDatasets"),
            "spaces": data.get("numSpaces"),
            "profile_url": f"https://huggingface.co/{args.username}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
