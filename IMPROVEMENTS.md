# Improvement Checklist

Items are ordered by impact within each section. Complete top-to-bottom.

## Already done
- [x] Blocklist (`blocklist.json`) — suppress known false positives before OSINT and scoring
- [x] Ground truth feedback loop (`outcomes.py`) — seed/review/tag/report pipeline; auto-seeded by `auto_monitor.py`

---

## Falcon / data quality


---

## Scoring

- [x] **Configurable thresholds** — All point values and dollar cutoffs are hardcoded. Move them to a `config.yaml` (or a `SCORING` dict at the top of `scoring.py`) so you can tune without editing source. Fields: `direct_entity_match_pts`, `large_trade_usd`, `falcon_min_pnl`, `falcon_min_win_rate`, etc.
- [x] **Penalise pure-polywhaler alerts** — If the only flag is `polywhaler_insider_score` (no OSINT or Falcon corroboration), subtract 3 points or add a `low_confidence` flag. Prevents Polywhaler's score from dominating when we have no independent signal.
- [x] **No-profile ghost penalty fix** — `osint_ran` check (line ~581) is broken: it requires both `sherlock_claimed is not None` and `"osint_ran" in profile`, but `"osint_ran"` is never written to the profile JSON. Audit and fix the condition so ghost-account detection actually fires.

---

## Pipeline reliability

- [x] **Telegram retry with backoff** — `post_telegram()` re-raises immediately on any non-400 HTTP error. Add exponential backoff (3 attempts, 2/4/8 s) before raising, so transient Telegram outages don't fail the whole run.
- [x] **Telegram deduplication** — If the same trader appears in multiple markets the same day they generate separate alert lines. Collapse into one entry per trader with all markets listed before sending.
- [x] **Polywhaler API fallback** — If all 3 retry attempts fail in `_get()`, fall back to the previous day's `trades.json` rather than crashing. Log that stale data is being used.
- [x] **Subprocess hard-failure guard** — `polywhaler_monitor.py` and `auto_monitor.py` both accept exit code 1 from subprocesses as "ok". Distinguish: exit 1 = partial/interrupted (acceptable), exit 2+ = crash (abort and log). Prevents scoring against corrupted partial data.

---

## OSINT / enrichment

- [x] **Trader profile persistence across runs** — Today, returning traders are re-enriched from `results/new_usernames/` only if their profile already exists there. Profiles from old dated runs (`results/polywhaler/YYYY-MM-DD/`) are not checked. Add a global `results/polywhaler_profiles/` cache that `polywhaler_monitor.py` writes to after each run, so any trader seen before retains their OSINT data.
- [x] **LinkedIn match confidence filter** — `_parse_linkedin_company()` accepts any snippet. Add a minimum-length check and reject snippets that are just job titles with no company (e.g. "Software Engineer" alone scores 0). Reduces noisy `investment_firm_company` flags.

---

## Observability

- [x] **Weekly precision digest** — Add a cron entry or `auto_monitor.py` flag (`--weekly-report`) that runs `outcomes.py report --days 7` and posts the output to Telegram alongside the daily alert. Closes the feedback loop without manual action.
- [x] **Run health summary** — At the end of each `auto_monitor.py` run, print (and optionally post) a one-line summary: traders fetched / new / scored / blocklisted / Falcon failures. Makes it easy to spot degraded runs at a glance.
