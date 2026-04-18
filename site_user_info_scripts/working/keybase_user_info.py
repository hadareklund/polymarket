#!/usr/bin/env python3
"""Fetch user profile information from Keybase public API."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from common import fetch_json, print_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Get Keybase user info by username.")
    parser.add_argument("username", help="Keybase username")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds")
    return parser.parse_args()


def _compact_proofs(proofs: list[dict]) -> list[dict[str, str | int | None]]:
    compact: list[dict[str, str | int | None]] = []
    for proof in proofs:
        if not isinstance(proof, dict):
            continue
        compact.append(
            {
                "type": proof.get("proof_type"),
                "username": proof.get("nametag"),
                "state": proof.get("state"),
                "service_url": proof.get("service_url"),
            }
        )
    return compact


def main() -> int:
    args = parse_args()
    endpoint = (
        "https://keybase.io/_/api/1.0/user/lookup.json"
        f"?usernames={quote(args.username)}"
    )
    try:
        data = fetch_json(endpoint, timeout=args.timeout)
        them = data.get("them") or []
        if not them:
            raise RuntimeError("User not found.")
        user = them[0]

        basics = user.get("basics") or {}
        profile = user.get("profile") or {}
        proofs_summary = user.get("proofs_summary") or {}
        proofs = proofs_summary.get("all") or []

        result = {
            "site": "Keybase",
            "username": basics.get("username") or args.username,
            "full_name": profile.get("full_name"),
            "bio": profile.get("bio"),
            "location": profile.get("location"),
            "proofs": _compact_proofs(proofs),
            "cryptocurrency_addresses": user.get("cryptocurrency_addresses") or [],
            "public_keys": user.get("public_keys") or {},
            "profile_url": f"https://keybase.io/{quote(args.username)}",
        }
        print_json(result)
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
