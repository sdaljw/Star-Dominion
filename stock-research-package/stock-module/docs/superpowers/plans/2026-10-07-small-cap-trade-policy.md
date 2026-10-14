# Small-Cap Trade Policy Implementation Plan

**Goal:** Replace the primary return study with causal first-confirmation dip-entry and board-aware exits.

**Architecture:** A pure daily-bar simulator consumes a signal index and explicit execution assumptions. A read-only worker replays existing V4 signal prefixes, attaches dated sector evidence, separates the requested cohort from the unfiltered diagnostic, and writes auditable artifacts.

**Tech Stack:** Python 3.11, existing Pydantic models, dataclasses, standard-library CSV/JSON/statistics, pytest.

User authorized immediate execution; no approval gate, unrelated changes or commits.

## Task 1: Trading State Machine

- [x] Add `backend/tests/test_small_cap_backtest.py` with real OHLCV bars. Assert first-touch fixed-price fill, no retrospective minimum, no T+0 exit, sealed-board priority, next-open break execution, fee-aware profit exits, timeout, blocked sells and censored positions.
- [x] Run `python -m pytest tests/test_small_cap_backtest.py -q` from backend; verify the missing simulator causes failure.
- [x] Implement `TradePolicy`, `TradeReplay`, and `replay_trade(stock, signal_index, policy)` in `backend/app/domain/small_cap_backtest.py`.
- [x] Repeat targeted tests until green. Validate finite inputs, dated ordered bars and positive costs/prices.

## Task 2: Causal Cohort Replay

- [x] Add `backend/tests/test_small_cap_policy_worker.py`: synthetic V4 probe-confirmation fixture, later alert days excluded, future sector history rejected, missing coverage produces null metrics, active orders block repeated entries, tail trades remain visible.
- [x] Run worker tests before implementation; verify missing functions fail.
- [x] Implement `collect_signals(stocks, history, start_date)` and `run_cohort(signals, stocks, policy, require_sector)` in `backend/workers/backtest_small_cap_policy.py`. Strict eligibility uses same-day confirmation-sector evidence, never an automatic fallback.
- [x] Add argparse paths/start/dip/fees/slippage/diagnostic switch; output report JSON, signal CSV and trade CSV with source hashes. Use mature signals with at least 33 following bars for primary statistics.
- [x] Run focused tests and actual command: `python -m workers.backtest_small_cap_policy --include-unfiltered-diagnostic --output-dir ../data/local-run-20261007/trade-policy`.

## Task 3: Delivery

- [x] Write `docs/small-cap-trade-policy-20261007.md` using measured counts and limitations, link it from the previous shortlist report and README. Retain fixed-horizon results as an explicitly superseded historical benchmark.
- [x] Run full backend pytest and scoped `git diff --check`. Inspect report and CSV, verify actual dataset was not modified and no synthetic evidence entered production caches.

Verification: 45 new focused tests; 324 full backend tests passed, six existing httpx deprecation warnings. Real-data replay found 218 signals, all missing dated sector evidence; the requested sector cohort has null performance. The explicitly unfiltered mature diagnostic has 43 closed trades and eight unfilled orders. Input SHA256 matches after the run; 218 CSV/JSON rows agree; policy-invariant audit found zero violations. Independent review found early-history omissions and last-bar unresolved reservation release; both were reproduced by failing tests, fixed and fully retested. Actual cached results are unchanged. No frontend or production-cache change was required.
