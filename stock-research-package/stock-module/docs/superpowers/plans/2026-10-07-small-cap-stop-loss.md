# Small-Cap 7% Stop-Loss Implementation Plan

**Goal:** Add the requested fixed-cost 7% stop to the existing causal replay and rerun the same historical samples.

**Architecture:** Keep signal selection and sector eligibility unchanged. Add a standing stop from the first sellable session, with fee-aware trigger, T+1 deferral and lower-limit restrictions. Preserve a separately generated disabled-stop baseline and never cap actual losses artificially.

**Tech Stack:** Existing Python dataclasses/Pydantic models, Decimal for tick rounding, pytest, JSON/CSV worker.

User authorized immediate implementation without further design approval; no commits or live trading.

- [x] Add failing tests in `backend/tests/test_small_cap_backtest.py`: intraday touch before a later sealed board, gap below stop, T+1, locked lower limit, costs, priority over queued profit/timeout, disabled baseline, and prohibition on retroactive stop tagging after an open sale.
- [x] Implement optional `stop_loss_pct=.07`, trigger price/index and exit timing in `backend/app/domain/small_cap_backtest.py`; validate rates and retain unresolved stop orders. Net-return calculation must continue using actual simulated proceeds, not an arbitrary -7% clamp.
- [x] Test and add worker `--stop-loss-pct` / `--no-stop-loss`, policy version 2 and stop trigger date in `backend/workers/backtest_small_cap_policy.py`.
- [x] Run focused tests, full backend tests, and real-data replay both with the default stop and with `--no-stop-loss --output-dir ../data/local-run-20261007/trade-policy-no-stop`.
- [x] Update the main report and README with measured comparisons, unresolved positions, T+1/limit-down exceptions and unchanged missing-sector qualification; inspect input hashes and ledger invariants.

Verification: 21 additional stop-policy tests, 66 focused tests total, 345 full backend tests passed with six existing httpx warnings. Independent review found an unsellable zero-volume breach did not retain its stop; reproduced with failing tests, fixed and rerun. Both real-data reports use the same immutable snapshot SHA256 and 218 signals. Mature cohort: 43 closed trades, mean net return 1.5539% without stop versus 1.2460% with stop, worst -33.0152% versus -7.0450%. Full-window stop version includes a T+1 loss of -9.0625%; no hard loss cap was fabricated. Strict dated-sector eligibility remains zero because coverage is missing. No production snapshot or live trading was changed.
