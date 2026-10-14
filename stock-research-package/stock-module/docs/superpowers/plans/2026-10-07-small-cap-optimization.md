# Small-Cap Return Optimization Implementation Plan

> **For agentic workers:** Execute inline using executing-plans and TDD; request an independent review after implementation. User authorized direct execution without additional approval. No commits or worktree changes.

**Goal:** Compare a frozen, limited set of small-cap entry refinements without changing the user's 7% stop or misrepresenting missing sector history.

**Architecture:** A read-only worker reuses the V4 signal scanner and existing trade replay. Truncate training prices at the validation boundary, select using training-only mature statistics, then report the single selected candidate's later-period result with opportunity-adjusted metrics and paired date-cluster uncertainty.

**Tech Stack:** Python dataclasses, standard-library statistics/random/JSON/CSV, existing Pydantic models, pytest.

## Task 1: Guardrails and Research Worker

Files: create `backend/tests/test_small_cap_optimization_worker.py` and `backend/workers/optimize_small_cap_policy.py`.

- [x] Add failing tests for frozen candidates, factor filtering, truncation, mature opportunity denominator, training-only selection, incomplete trades and paired date resampling. Example contracts:

```python
assert worker.Trial("shallow", max_drawdown_pct=6).accepts({"max_drawdown_pct": 6})
assert not worker.Trial("shallow", max_drawdown_pct=6).accepts({})
assert worker.opportunity_metrics([], 20)["return_per_original_signal_pct"] is None
```

- [x] Run `python -m pytest tests/test_small_cap_optimization_worker.py -q`; missing worker produced expected failures. Corrected the test fixture import to use the existing `tests` package.
- [x] Implement `Trial`, `TRIALS`, `truncate_stocks`, `opportunity_metrics`, `select_training_trial`, `paired_date_interval`, `run_experiment` and CLI. Use the existing `run_cohort` for reservations/exits; keep `TradePolicy(stop_loss_pct=.07)` unchanged and outputs outside inputs.
- [x] Rerun the focused tests and the existing replay/worker tests; 95 passed, including29 new optimization cases.

## Task 2: Actual Data and Independent Review

Files: generated `data/local-run-20261007/trade-policy-optimization/` only; no input or production cache writes.

- [x] Run `python -m workers.optimize_small_cap_policy --include-unfiltered-diagnostic`. Training prices end before June26; validation starts June26; record all11 trials without selecting from validation. Final run has829 training and218 later signals,737/51 mature original signals; all11 mature training trade means are negative, no winner selected.
- [x] Request read-only independent review of the worker/tests for future leakage, biased opportunity denominators, false recommendations and missing historical sector evidence. Resolve valid findings with failing regression tests first. Fixed validation end propagation, rejection of undated/unordered bars and history read/hash consistency; follow-up reviewer reported no remaining high/medium issues. Both reviewers closed after completion.
- [x] Verify input SHA256, selected trial provenance, unchanged default stop and absence of late training outcomes; run full `python -m pytest -q` and targeted whitespace checks. 374 passed with6 pre-existing warnings; hash unchanged, no training sale after cutoff, previous mature baseline matches,1047 baseline CSV rows/44 trial rows/0 selected rows.

## Task 3: Evidence and Delivery

Files: create `docs/small-cap-optimization-20261007.md`; modify only the related research section of `README.md`.

- [x] Report actual training selection, later mature trade count, mean/median/net signal contribution, loss tails and interval. No training winner means selected monthly/cost stress reports remain empty; these paths are tested, not represented as actual evidence. Fixed2% sensitivity improves the later mean from1.2460% to1.6174% but not training, and its paired contribution interval crosses zero.
- [x] State formal sector coverage and data cutoff prominently. Keep production parameters unchanged; missing history makes all formal returns null, not zero. Main report andREADME link published.
- [x] Update this checklist with fresh test counts and audit results; show the report and give a concise Chinese outcome including limitations.
