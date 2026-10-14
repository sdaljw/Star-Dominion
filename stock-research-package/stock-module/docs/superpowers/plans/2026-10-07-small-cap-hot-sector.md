# Small-Cap Hot-Sector Entry Implementation Plan

> **For agentic workers:** Execute inline with TDD and requesting-code-review. User already authorized direct implementation without another approval. No commit or unrelated refactor.

**Goal:** Restrict entry candidates to the intersection of contemporaneous peer-sector effect and a documented hot-theme proxy.

**Architecture:** Extend point-in-time sector evidence and add one shared entry gate. Candidate ingestion annotates eligibility; the frontend separates entry from observation. Replay and optimization use the same gate for their main cohort while retaining explicitly labeled comparisons.

**Tech Stack:** Python/Pydantic/pytest, React/TypeScript/Vitest, existing Playwright verification.

## Task 1: Evidence and Gate

Files: `backend/app/domain/market_lines.py`, `probe_sector.py`, new `small_cap_entry.py`, `backend/app/integrations/candidate_sources.py`; tests in `backend/tests/test_probe_sector.py` and new `test_small_cap_entry.py`.

- [x] Add failing tests: rank10 passes/rank11 fails, missing basis is unknown, weak-hot plus strong-cold cannot combine, alternative hot line qualifies, old signal dates cannot borrow current evidence.
- [x] Run focused pytest to observe missing behavior; implement snapshot rank basis, independent hot evidence and shared gate. Contract:

```python
assert build_small_cap_entry_gate(factors)["entry_eligible"] is False
```

- [x] Ingestion attaches gate only after V4 and historical context. Retain noneligible setups as observation.

## Task 2: Replay and UI

Files: `backend/workers/backtest_small_cap_policy.py`, `optimize_small_cap_policy.py`, related worker tests; `frontend/src/components/SmallCapAbsorptionPanel.tsx`, `SmallCapFactors.tsx`, related tests.

- [x] Add failing tests for shared production/replay eligibility, main dual-filter cohort, separately labeled sector-only cohort, missing data/no fallback and input immutability.
- [x] Implement `require_hot_theme` with defaultFalse on helper APIs, mainCLITrue, versioned new output paths. Keep7% stop and trade execution unchanged.
- [x] Add failing frontend tests for defaultentry, observation with active volume but missing theme, legacycache and stale source exclusion. Implement tabs and evidence readout using existing styles.
- [x] Run targeted and full tests, `npm run build`, and real-data research commands.

## Task 3: Review and Verification

Files: report `docs/small-cap-hot-sector-20261007.md`, scopedREADME update; generated outputs only under `data/local-run-20261007/`.

- [x] Request independent read-only review of evidence selection, AND semantics, timestamps, stale/legacy gates and replay consistency; reproduce findings before fixing. Final bounded recheck found no further direct regression.
- [x] Verify Playwright desktop/mobile nonblank, tab interactions, nooverflow and actual eligibility/unknown states with isolatedUI fixtures, never fake production history.
- [x] Audit input hash, unchanged original timestamps, cohortcoverage and CSV rows. Report unavailable formal performance honestly, update checklist and open report (Codex panel queued successfully).

## Verification Record

- Backend: 411 passed, 6 existing httpx deprecation warnings. Frontend: 82 passed; build passed.
- Reproduced and repaired acquisition-time laundering, unknown-rank renumbering, top-five evidence loss, persisted failure/restart, multi-instance consistency and mixed-version reads; gate version2 invalidates pre-fix eligibility caches.
- Actual cache: 108 observations, 0 eligible, original generated timestamp retained; other source payloads unchanged. Missing dated history remains missing, not backfilled.
- Research: policy v3 and optimization v2 replay completed, formal/sector-only returns null; explicit unfiltered baseline unchanged. Input SHA256 verified, all CSV counts audited.
- Playwright: 1440x1000 and 390x844, no page errors/overflow/factor overlap; test evidence and authentication only mocked in isolated browser contexts.
