#!/usr/bin/env python3
"""Run Sherlock against a fixed set of target sites for one or more usernames."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

TARGET_SITES = [
    "LinkedIn",
    "GitHub",
    "StackOverflow",
    "ResearchGate",
    "Medium",
    "Pastebin",
    "Rentry",
    "Doxbin",
    "BitcoinTalk",
    "Reddit",
    "TradingView",
    "HackerNews",
    "Twitter",
    "Telegra.ph",
    "Discord",
    "Keybase",
    "AngelList",
    "Crunchbase",
    "Substack",
    "Quora",
    "Mixcloud",
    "chess.com",
    "Cashapp",
]

# Manual aliases for names that differ from Sherlock's manifest keys.
TARGET_SITE_ALIASES = {
    "mixcloud": "MixCloud",
    "chess.com": "Chess",
    "cashapp": "CashApp",
}


class SilentQueryNotify:
    """Minimal notifier compatible with Sherlock's expected interface."""

    def start(self, message=None) -> None:
        return

    def update(self, result) -> None:
        return

    def finish(self, message=None) -> None:
        return


def normalize_site_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def ensure_local_sherlock_importable(script_dir: Path) -> None:
    sherlock_root = script_dir / "sherlock"
    if not sherlock_root.exists():
        raise FileNotFoundError(
            f"Could not find local Sherlock folder at: {sherlock_root}"
        )
    if str(sherlock_root) not in sys.path:
        sys.path.insert(0, str(sherlock_root))


def ensure_tomli_compatibility() -> None:
    """Provide a tomli-compatible module on Python 3.11+ if needed."""
    try:
        import tomli  # noqa: F401
    except ModuleNotFoundError:
        try:
            import tomllib
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Missing 'tomli' module and no stdlib 'tomllib' available."
            ) from exc
        sys.modules["tomli"] = tomllib


def load_usernames(args: argparse.Namespace) -> list[str]:
    usernames: list[str] = []

    if args.usernames_file:
        path = Path(args.usernames_file)
        if not path.exists():
            raise FileNotFoundError(f"Usernames file not found: {path}")
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if line and not line.startswith("#"):
                usernames.append(line)

    if args.usernames:
        usernames.extend(args.usernames)

    # Preserve order while removing duplicates.
    seen: set[str] = set()
    deduped: list[str] = []
    for username in usernames:
        if username not in seen:
            seen.add(username)
            deduped.append(username)

    return deduped


def resolve_sites(
    requested: Iterable[str],
    available_site_names: Iterable[str],
) -> tuple[list[str], list[str]]:
    available = list(available_site_names)
    lower_index = {site.lower(): site for site in available}

    normalized_index: dict[str, list[str]] = {}
    for site in available:
        normalized = normalize_site_name(site)
        normalized_index.setdefault(normalized, []).append(site)

    resolved: list[str] = []
    missing: list[str] = []

    for requested_name in requested:
        alias_target = TARGET_SITE_ALIASES.get(requested_name.lower())
        selected: str | None = None

        if alias_target:
            selected = lower_index.get(alias_target.lower())

        if selected is None:
            selected = lower_index.get(requested_name.lower())

        if selected is None:
            normalized_requested = normalize_site_name(requested_name)
            candidates = normalized_index.get(normalized_requested, [])
            if len(candidates) == 1:
                selected = candidates[0]

        if selected is None:
            missing.append(requested_name)
            continue

        if selected not in resolved:
            resolved.append(selected)

    return resolved, missing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Search usernames with Sherlock against a fixed set of target sites. "
            "You can pass usernames directly and/or via --usernames-file."
        )
    )
    parser.add_argument(
        "usernames",
        nargs="*",
        help="Usernames to search.",
    )
    parser.add_argument(
        "--usernames-file",
        help="Path to a text file with one username per line.",
    )
    parser.add_argument(
        "--output",
        default="targeted_sherlock_results.json",
        help="Output JSON report path (default: targeted_sherlock_results.json)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="Request timeout in seconds for each site check (default: 20)",
    )
    parser.add_argument(
        "--print-all",
        action="store_true",
        help="Print all checked site statuses, not only claimed results.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.timeout <= 0:
        print("Error: --timeout must be > 0", file=sys.stderr)
        return 2

    script_dir = Path(__file__).resolve().parent

    try:
        ensure_local_sherlock_importable(script_dir)
        ensure_tomli_compatibility()
        from sherlock_project.sherlock import sherlock
        from sherlock_project.sites import SitesInformation

        usernames = load_usernames(args)
        if not usernames:
            print(
                "Error: provide at least one username via CLI args or --usernames-file.",
                file=sys.stderr,
            )
            return 2

        local_manifest = (
            script_dir / "sherlock" / "sherlock_project" / "resources" / "data.json"
        )
        sites = SitesInformation(
            data_file_path=str(local_manifest),
            honor_exclusions=False,
        )
        site_data_all = {site.name: site.information for site in sites}

        resolved_sites, missing_sites = resolve_sites(
            TARGET_SITES, site_data_all.keys()
        )
        if not resolved_sites:
            print(
                "Error: none of the requested target sites were found in this Sherlock manifest.",
                file=sys.stderr,
            )
            return 1

        site_data = {
            site_name: site_data_all[site_name] for site_name in resolved_sites
        }

        if missing_sites:
            print(
                "Warning: these requested sites are not in the current local Sherlock manifest:",
                file=sys.stderr,
            )
            print("  " + ", ".join(missing_sites), file=sys.stderr)

        print(
            f"Running Sherlock for {len(usernames)} username(s) across {len(resolved_sites)} site(s)...",
            file=sys.stderr,
        )

        report: dict[str, object] = {
            "requested_sites": TARGET_SITES,
            "resolved_sites": resolved_sites,
            "missing_sites": missing_sites,
            "results": [],
        }

        for username in usernames:
            query_notify = SilentQueryNotify()
            results = sherlock(
                username=username,
                site_data=site_data,
                query_notify=query_notify,
                timeout=args.timeout,
            )

            found_entries: list[dict[str, str]] = []
            full_entries: list[dict[str, str]] = []

            for site_name in resolved_sites:
                site_result = results[site_name]
                status_obj = site_result["status"]
                status_name = status_obj.status.value
                url_user = site_result["url_user"]

                entry = {
                    "site": site_name,
                    "status": status_name,
                    "url": url_user,
                }
                full_entries.append(entry)

                if status_name == "Claimed":
                    found_entries.append(entry)

            report["results"].append(
                {
                    "username": username,
                    "found_count": len(found_entries),
                    "found": found_entries,
                    "all": full_entries,
                }
            )

            print(f"\n[{username}]", file=sys.stderr)
            if found_entries:
                for found in found_entries:
                    print(f"  + {found['site']}: {found['url']}", file=sys.stderr)
            else:
                print(
                    "  (no claimed profiles found on resolved target sites)",
                    file=sys.stderr,
                )

            if args.print_all:
                for item in full_entries:
                    print(f"  - {item['site']}: {item['status']}", file=sys.stderr)

        output_path = Path(args.output)
        output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote report to: {output_path}", file=sys.stderr)
        return 0

    except ModuleNotFoundError as exc:
        print(
            "Error: missing dependency while importing Sherlock modules. "
            "Try: python3 -m pip install -e ./sherlock",
            file=sys.stderr,
        )
        print(f"Details: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
