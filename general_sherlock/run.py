#!/usr/bin/env python3
"""
Run sherlock on every username in a file and aggregate results.

Usage:
    python3 run.py usernames.txt
    python3 run.py usernames.txt --timeout 1
    python3 run.py usernames.txt --timeout 1 --output-dir ./out
"""

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
HIT_RE = re.compile(r"\[\+\]\s+(.+?):\s+(https?://\S+)")


SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"


def find_python() -> str:
    """Return the Python that has sherlock_project available."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def read_usernames(path: Path) -> list[str]:
    usernames = []
    for line in path.read_text(encoding="utf-8").splitlines():
        u = line.strip()
        if u and not u.startswith("#"):
            usernames.append(u)
    return usernames


def run_sherlock(python_bin: str, username: str, timeout: int) -> list[tuple[str, str]]:
    cmd = [python_bin, "-m", "sherlock_project", "--print-found", "--no-color", "--timeout", str(timeout), username]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(timeout * 600, 120))
        output = ANSI_RE.sub("", proc.stdout + proc.stderr)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        print(f"  [warn] sherlock failed for {username}: {e}", file=sys.stderr)
        return []
    return [
        (m.group(1).strip(), m.group(2).strip())
        for line in output.splitlines()
        if (m := HIT_RE.match(line))
    ]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sherlock batch runner — aggregates results and site statistics."
    )
    parser.add_argument("file", help="Text file with one username per line")
    parser.add_argument(
        "--timeout",
        type=int,
        default=1,
        help="Per-site timeout in seconds passed to sherlock (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for output files (default: same directory as input file)",
    )
    args = parser.parse_args()

    python_bin = find_python()

    usernames_path = Path(args.file).resolve()
    if not usernames_path.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    usernames = read_usernames(usernames_path)
    if not usernames:
        print("Error: no usernames found in file", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(args.output_dir).resolve() if args.output_dir else usernames_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    stem = usernames_path.stem
    results_file = output_dir / f"{stem}_results.txt"
    stats_file = output_dir / f"{stem}_stats.txt"

    site_counts: Counter = Counter()
    all_results: dict[str, list[tuple[str, str]]] = {}

    print(f"python: {python_bin}", file=sys.stderr)
    print(f"Searching {len(usernames)} usernames (timeout={args.timeout}s)...", file=sys.stderr)

    for i, username in enumerate(usernames, 1):
        print(f"[{i}/{len(usernames)}] {username}", file=sys.stderr, end="", flush=True)
        hits = run_sherlock(python_bin, username, args.timeout)
        all_results[username] = hits
        for site, _ in hits:
            site_counts[site] += 1
        print(f"  → {len(hits)} hits", file=sys.stderr)

    # All results
    with results_file.open("w", encoding="utf-8") as f:
        f.write(f"Sherlock results for {len(usernames)} usernames\n")
        f.write(f"Input file: {usernames_path}\n")
        f.write("=" * 60 + "\n\n")
        for username, hits in all_results.items():
            f.write(f"[{username}]  ({len(hits)} hits)\n")
            for site, url in sorted(hits, key=lambda x: x[0].lower()):
                f.write(f"  {site}: {url}\n")
            f.write("\n")

    # Statistics
    with stats_file.open("w", encoding="utf-8") as f:
        f.write(f"Sherlock site statistics\n")
        f.write(f"Input file: {usernames_path}\n")
        f.write(f"Usernames searched: {len(usernames)}\n")
        f.write(f"Unique sites with hits: {len(site_counts)}\n")
        f.write("=" * 60 + "\n\n")
        f.write(f"{'Site':<40} {'Hits':>6}  {'% of users':>10}\n")
        f.write("-" * 60 + "\n")
        for site, count in site_counts.most_common():
            pct = count / len(usernames) * 100
            f.write(f"{site:<40} {count:>6}  {pct:>9.1f}%\n")

    total_hits = sum(len(h) for h in all_results.values())
    print(f"\nDone. {total_hits} total hits across {len(site_counts)} sites.", file=sys.stderr)
    print(f"Results → {results_file}", file=sys.stderr)
    print(f"Stats   → {stats_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
