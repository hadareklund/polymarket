# Improvement Checklist — Round 2

Items are grounded in the actual code and ordered by impact within each section.
The purpose of the system is to surface traders who likely have material non-public
information so the operator can decide whether to mirror their position. Every
improvement below is evaluated against that goal: does it increase precision (fewer
false positives) or recall (catch more real insiders)?

---

## Signal quality — making existing signals more reliable

- [ ] **Falcon: minimum trade count for win-rate and Sharpe validity** — `falcon_high_win_rate`
  fires at ≥75% win rate regardless of sample size; 3 wins out of 4 trades is 75% but
  meaningless. `falcon_high_sharpe` has the same problem — a Sharpe of 2.4 over 7 days
  and 8 trades is noise. Add two new SCORING keys: `falcon_min_win_rate_trades: 15` and
  `falcon_min_sharpe_trades: 20`. Gate both flags on these minimums. Use
  `w360.get("total_trades")` (available in the 360 response) for the count. This is the
  single highest-leverage fix to reduce false positives from lucky short-run traders.

- [ ] **Falcon: score the leaderboard rank (agent 579 is already fetched but never used)** —
  `enrich_wallet()` in `falcon_analytics.py` calls agent 579 and stores the result under
  `top_traders_leaderboard` in the profile, but nothing in `scoring.py` reads it. A trader
  ranked in the top 100 on the lifetime leaderboard + concentrated bet is a very strong
  independent signal. Add a `falcon_leaderboard_top100` flag (3 pts) and
  `falcon_leaderboard_top500` flag (1 pt) to `falcon_flags()`. The rank field from agent
  579 is `rank` inside the response dict.

- [ ] **Falcon: score `days_active` as an account-age proxy** — Agent 581 returns
  `days_active` in the 360 response but it is never scored. A wallet with <30 days active
  + concentrated bet + large trade is a fresh burner account — exactly the shape of an
  insider who opened an account just to place this bet. Add a `new_account` flag (2 pts)
  gated on `days_active < 30 and total_trades < 10`. Add threshold keys to SCORING.

- [ ] **Username uniqueness: penalise matches on generic names** — A "direct_entity_match"
  or any OSINT signal carries much less weight when the Polymarket username is "john",
  "crypto", or "trader1" — the GitHub/HuggingFace account found is almost certainly a
  different person. Add a helper `_username_is_generic(name: str) -> bool` that flags
  names shorter than 5 chars, entirely numeric, or matching a common-word list. Apply a
  `-4` confidence penalty (`low_identity_confidence` flag) when the username is generic
  and the only OSINT match is via that username rather than a verified real name.

- [ ] **Category keywords: narrow the science tier** — The current science keywords include
  "pharmaceutical", "clinical trial", "biotech", "research institute" — these are so broad
  that a software engineer at a med-tech startup would score 8 pts for a CDC market bet.
  Split into `science_direct` (CDC, NIH, FDA, WHO — score 8) and `science_adjacent`
  (pharmaceutical, biotech, clinical trial — score 3) to reduce noise. Store the two tiers
  in SCORING so they're tunable.

- [ ] **Require corroboration when LinkedIn is the only source** — If the only OSINT signal
  is a LinkedIn snippet (not `.company` field but `.snippet`) and no other professional
  site has been found, the match confidence is low because snippets are search-result blurbs
  that often mention prior employers or clients. Add a `linkedin_snippet_only` penalty
  (-2 pts) when `direct_entity_match` fires via `LinkedIn.snippet` but the profile has no
  GitHub, HuggingFace, or Keybase profiles to corroborate identity.

---

## New signals — net-new data points not currently used

- [ ] **GitHub repository names as direct entity signal** — `run.py`'s GitHub scraper
  collects `repos` (the trader's repository list), but `scoring.py`'s `prof_fields_from_site()`
  only extracts `bio` and `company`. A trader who has committed to `anthropic/anthropic-sdk`
  or has a repo named `stripe-internal-tools` is a much stronger signal than a bio mention.
  Add a `GitHub.repo_names` field extracted from the `repos` list in the site profile, and
  run `kw_match()` against it in `score_against_market()`. This is also useful in
  `analyze_insider_trading.py` for the IPO pipeline.

- [ ] **Cross-site profile consistency check** — Currently a Polymarket username match to
  a GitHub profile is treated as certain, but "johndoe" on GitHub might be a different
  person from "johndoe" on Polymarket. A simple heuristic: if the same real name appears
  on 2+ professional sites (GitHub name = Hugging Face full_name = LinkedIn search name),
  that is a much higher-confidence identity match than a single-site username match.
  Compute an `identity_confidence` score (0=username-only, 1=single real name,
  2=name+location match, 3=name on 2+ pro sites) and multiply flag points accordingly,
  e.g. × 0.5 for identity_confidence=0, × 1.0 for ≥1. Store as a profile field so it
  feeds the Claude brief.

- [ ] **Multiple correlated bets in same market direction as signal** — `all_trades` is
  already collected per trader (list of every market they bet on), but no logic checks
  whether all their bets are in the same thematic cluster (e.g. all YES on AI-company IPOs,
  or all YES on specific-politician-wins markets). A trader betting YES on 4 different AI
  markets with no crypto/politics hedging is more suspicious than one with a diverse book.
  In the scoring loop, after populating `result["all_trades"]`, compute a `theme_cluster`
  score: if ≥3 trades share the same category and same outcome, add a `thematic_concentration`
  flag (2 pts) to the result.

- [ ] **Bet entry price as signal** — The Polymarket trades include the price at which the
  bet was placed (or this can be inferred from `size` and `shares` in the trade object).
  A trader buying YES at 5% probability is making an extreme contrarian bet — if they are
  right, the implied return is 20× and the timing signal is very strong. Score entry price
  as a bonus: `entry_price < 0.10` → +2 pts (`low_probability_conviction`), `entry_price
  < 0.05` → +3 pts. The trade object from polywhaler includes enough data to compute this
  (`outcome_price` or similar field — verify against the raw JSON).

- [ ] **Profile staleness: re-OSINT returning traders whose cache is old** — The global
  `results/polywhaler_profiles/` cache persists profiles indefinitely, but a profile written
  6 months ago may be missing a new LinkedIn job or a GitHub employer change — exactly the
  kind of update that would change the score. Add a `last_osint_at` timestamp to profile
  JSON when it is written, and in `polywhaler_monitor.py`'s main loop, if a returning trader's
  profile is older than `--osint-refresh-days` (default 30), add them to the `new_usernames`
  list for a re-OSINT run instead of using the cached profile.

---

## Pipeline intelligence — smarter orchestration

- [ ] **Multi-engine LinkedIn fallback** — When `linkedin_batch.py` is called with `--engine
  brave` and the Brave quota is exhausted mid-run, the remaining entries are silently
  skipped. The script should detect `RuntimeError("monthly_quota_exceeded")` and
  automatically restart remaining queries with `--engine google` (if `GOOGLE_API_KEY` is
  set) or `--engine bing` as a last resort. This keeps LinkedIn enrichment running at full
  throughput regardless of Brave quota state. Change `search_for_linkedin()` to accept a
  list of engines and try them in order.

- [ ] **Inject current market probability into the Claude brief** — Claude currently receives
  the flag data and on-chain metrics but has no idea what the market probability was when
  the trade was placed or what it is now. If a trader bought YES at 12% and the market is
  now at 78%, that is powerful post-hoc validation of their information advantage. Fetch
  current market prices from the Gamma API (`https://gamma-api.polymarket.com/markets?slug=…`)
  in `build_prompt()` and add `market_prob_at_trade` and `market_prob_current` fields to
  each trader summary passed to Claude. The market slug is available from the trade object.

- [ ] **Blocklist auto-scoring: add a `reason` field and populate known market makers** —
  `blocklist.json` is empty and the format uses dicts for both `wallets` and `usernames`
  but the values are empty objects `{}`. The dict format supports per-entry metadata (e.g.
  `{"reason": "market_maker", "added": "2026-05-01"}`). Add a script or a `polywhaler_monitor.py`
  flag (`--add-blocklist <wallet_or_username> --reason <text>`) that writes entries to
  `blocklist.json` with provenance. Also add an automatic check: if a wallet appears in the
  polywhaler top-10 most-traded list every day for 30+ days, flag it for review as a likely
  market maker and suggest adding to the blocklist.

- [ ] **Score deduplication within a single day's trades** — A trader who placed 8 separate
  trades in the same market on the same day shows up with 8 entries in `trades.json`, all
  deduped to one scorer entry (their best trade). But the `all_trades` list only shows
  cross-market trades, not the intra-day accumulation in one market. Accumulate the total
  USD value across all same-market trades for scoring the `large_trade` threshold — a trader
  who placed 8 × $15k buys (total $120k) in one market should score `large_trade`, not 8 ×
  `medium_trade`. Group by `(username, market slug)` before scoring.

- [ ] **Telegram brief: separate summary (short) from full report (file)** — The Claude
  analysis is capped at 1000 characters to fit Telegram, which often forces Claude to drop
  lower-scored traders who still warrant attention. Write the full uncapped analysis to
  `claude_analysis.txt`, then generate a second short prompt asking Claude to produce a
  ≤1000-char Telegram summary of the top 3 traders only. This gives the operator both a
  quick push notification and a readable file for deeper review.

---

## Feedback loop — closing the gap between alerts and outcomes

- [ ] **Precision-weighted flag scores based on outcomes history** — `outcomes.py report`
  already computes precision per flag type (e.g. `direct_entity_match_linkedin` at 67%,
  `falcon_high_win_rate` at 43%). This data should feed back into the scoring system.
  In `build_prompt()`, load `results/outcomes.json` and compute empirical precision per
  flag type (using only verdicts with ≥5 decided cases for statistical stability), then
  inject a `flag_precisions` dict into the Claude system prompt so it can apply its own
  judgment about which flags are reliable vs. noisy. Longer term, adjust SCORING values
  based on this data when ≥20 decided verdicts per flag type accumulate.

- [ ] **Auto-resolve pre-resolution timing flags when market settles** — Traders flagged for
  `pre_resolution_trade` (bet placed <60 min before close) should be automatically
  retroactively scored: if the market resolved in their favor (YES bet + YES resolution),
  this is strong post-hoc evidence. Add an `outcomes.py auto-resolve` sub-command that
  queries the Gamma API for all pending-verdict alerts where the market has since resolved,
  and automatically tags them `correct` (if bet matched resolution) or `false_positive`
  (if not), without waiting for manual review. This dramatically speeds up the feedback loop.

- [ ] **Outcomes seed: include flag type breakdown in Telegram brief** — When `auto_monitor.py`
  runs the weekly digest (`--weekly-report`), the `outcomes.py report --days 7` output is
  already formatted for the terminal. Improve it to include a per-flag-type table so the
  operator immediately sees which signals are paying off. The existing `cmd_report()` in
  `outcomes.py` already computes this data but formats it with Unicode block chars
  (`█░`) that may not render in Telegram — add a `--plain` flag that uses ASCII
  equivalents for the Telegram post.

- [ ] **Track score drift for returning traders** — When a trader appears in multiple daily
  runs, their score may change as new OSINT is discovered. Currently each run's `analysis.json`
  is independent; there is no longitudinal view. Add a `score_history` list to the global
  profile cache entry (capped at last 10 appearances), storing `{date, our_score, flags}`.
  Surface this in the Claude prompt as a trend: "trader was scored 8 pts last week, now 22
  pts — new LinkedIn data found." A rising score over multiple appearances strengthens the
  case for copying.

---

## Operational improvements

- [ ] **Cron: add Monday `--weekly-report` variant** — The weekly digest flag was added to
  `auto_monitor.py` but the cron entry in CLAUDE.md still runs the plain daily command.
  Add a second cron line that runs every Monday at 08:30 UTC with `--weekly-report`, so
  the feedback digest lands automatically each week without manual intervention.

- [ ] **State file locking to prevent concurrent-run corruption** — `state.json` is written
  with a rename-into-place pattern (`.tmp` → final) which is atomic, but `load_state()` and
  `save_state()` can still race if two processes run concurrently (e.g. cron + manual run).
  Wrap `save_state()` with a `fcntl.flock` exclusive lock on a `.lock` sidecar file.
  Release on exit. If the lock cannot be acquired within 30 seconds, abort with a clear
  error message.

- [ ] **Checkpoint stale-lock detection in run.py** — `checkpoint.json` is written per
  username file stem. If a previous run crashed mid-way and left a checkpoint, the next run
  correctly resumes. But if the username file changes (new trader added to same file), the
  old checkpoint may mark some users as done incorrectly. Add a `file_hash` field to the
  checkpoint recording the MD5 of the usernames file at checkpoint creation; invalidate the
  checkpoint if the hash doesn't match on resume.

- [ ] **CLAUDE.md: document the SCORING dict as the tuning interface** — The SCORING dict
  in `scoring.py` is the primary way to tune the system's sensitivity, but CLAUDE.md only
  documents the hardcoded values from before Round 1. Update the scoring table in CLAUDE.md
  to note that all values are now configurable via `scoring.SCORING` and list the dict keys
  alongside their current defaults, so future operators don't have to read the source to
  know what's tunable.
