#!/usr/bin/env python3
"""Run all working site scrapers for a username and save combined JSON output.

Usage:
    python3 run_working.py <username> [--out result.json] [--timeout 20] [--skip-error]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKING_DIR = Path(__file__).resolve().parent / "site_user_info_scripts" / "working"


def discover_scripts() -> list[Path]:
    return sorted(WORKING_DIR.glob("*_user_info.py"))


def run_script(script: Path, username: str, timeout: int) -> dict:
    site = script.stem.replace("_user_info", "")
    try:
        proc = subprocess.run(
            [sys.executable, str(script), username, "--timeout", str(timeout)],
            capture_output=True,
            text=True,
            timeout=timeout + 10,
        )
        if proc.returncode != 0:
            return {
                "site": site,
                "status": "error",
                "reason": proc.stderr.strip() or f"exit code {proc.returncode}",
            }
        return json.loads(proc.stdout)
    except subprocess.TimeoutExpired:
        return {"site": site, "status": "error", "reason": f"timed out after {timeout}s"}
    except json.JSONDecodeError as exc:
        return {"site": site, "status": "error", "reason": f"invalid JSON output: {exc}"}
    except Exception as exc:
        return {"site": site, "status": "error", "reason": str(exc)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all working scrapers for a username.")
    parser.add_argument("username", help="Username to look up")
    parser.add_argument("--out", help="Output JSON file (default: results/<username>_results.json)")
    parser.add_argument("--timeout", type=int, default=30, help="Per-script timeout in seconds")
    parser.add_argument("--skip-error", action="store_true", help="Omit error results from output")
    args = parser.parse_args()

    scripts = discover_scripts()
    if not scripts:
        print(f"No scripts found in {WORKING_DIR}", file=sys.stderr)
        return 1

    results_dir = Path(__file__).resolve().parent / "results"
    results_dir.mkdir(exist_ok=True)
    out_path = Path(args.out) if args.out else results_dir / f"{args.username}_results.json"

    combined = {
        "username": args.username,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "results": {},
    }

    for script in scripts:
        site = script.stem.replace("_user_info", "")
        print(f"  → {site}...", file=sys.stderr)
        result = run_script(script, args.username, args.timeout)
        if args.skip_error and result.get("status") == "error":
            continue
        combined["results"][site] = result

    out_path.write_text(json.dumps(combined, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n✓ Saved to {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
