# Small-Cap Sector OR Hot Implementation Plan

> Execute inline with TDD. Prior user authorization permits direct implementation without another approval. No commits or unrelated refactors.

**Goal:** Active V4 signals enter with either dated sector effect or dated top-20 gain-ranked theme.

**Architecture:** Independent evidence, version3 shared gate with branch labels, shared replay eligibility and opt-in OR helper flag. Preserve trading execution and existing failure/freshness safeguards.

**Tech Stack:** Python/Pydantic/pytest; React/TypeScript/Vitest; isolated Playwright.

- [x] Write and observe failing tests in `test_small_cap_entry.py`, `test_probe_sector.py`, policy/optimization worker tests and factor/panel tests: hot-only rank20 passes, rank21 fails, sector-only passes, invalid unused evidence cannot veto, cache v2 rejected.
- [x] Implement independent hot evidence in `probe_sector.py` and OR gate in `small_cap_entry.py`; ingestion already invokes this gate. Expected: `build_small_cap_entry_gate(hot_only)["entry_basis"] == "hot_theme_only"`.
- [x] Update worker helper qualifier and optimization denominator, set primary CLI OR with versioned output directories. Focused backend: 98 passed.
- [x] Update factor labels/metrics, empty-state wording and cache v3 check; use current styles. Frontend: 84 passed; build passed.
- [x] Run all backend tests and real backtest/optimization with explicit unfiltered diagnostic; keep actual history untouched and check SHA256/CSV counts. Backend: 421 passed. Diagnostic performance statistics unchanged; changed trade fields are eligibility metadata only.
- [x] Independently review OR, standalone hotness, chronology and research denominators. No actionable findings. Desktop/mobile three synthetic branches, detail metrics, stale/cache exclusion and layout passed. Actual cache: 108 observations, zero eligible, version3. Report saved; automatic opening omitted after user reported two Codex desktop crashes.

Completed 2026-10-08. Details: `docs/small-cap-sector-or-hot-20261007.md`; desktop crash investigation: `docs/codex-crash-investigation-20261008.md`. Root cause of desktop crashes remains unresolved; browser automation and image previews stopped.
