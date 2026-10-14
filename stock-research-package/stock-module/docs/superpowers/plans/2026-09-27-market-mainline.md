# Market Mainline Implementation Plan

## Task 1: Domain and history persistence

- [x] Add focused tests for ladder tiers, breadth thresholds, persistence labels, scoring, and top-five ordering.
- [x] Implement market-line domain models and scoring.
- [x] Add date-keyed, same-day-idempotent, 60-session atomic history repository tests and implementation.

## Task 2: Worker data pipeline

- [x] Capture ranked THS concept snapshots without adding another network call.
- [x] Derive main-board market breadth from the existing full-market quote frame.
- [x] Build and append only fresh, post-close market-line snapshots; leave successful history untouched on source failure.
- [x] Schedule an independently configurable weekday after-close refresh without changing the existing morning schedule.
- [x] Add worker tests for capture, eligibility, post-close gating, and failure preservation.

## Task 3: API

- [x] Add current snapshot freshness service and `GET /api/v1/market-line/current`.
- [x] Test fresh, stale, and unavailable responses, including HTTP 200 for unavailable.

## Task 4: Frontend

- [x] Add API/types and the full-width market-mainline panel.
- [x] Add exact-symbol contextual labels to strategy and small-cap candidates without changing their order or score.
- [x] Refresh mainline state with the existing candidate refresh flow.
- [x] Add focused component/API tests and verify production build.

## Task 5: Verification

- [x] Run the backend suite and frontend tests/build.
- [x] Review the working diff for accidental changes and report any unavailable runtime/browser verification.

## Verification Record

- Backend full suite: 242 passed before the final five-session calendar-window refinement; the final market-line/worker/API/THS focused suite passed 43 tests.
- Frontend: 72 tests passed; production TypeScript/Vite build passed. The final exact-symbol helper test also passed after its fixture was extended.
- `git diff --check` passed for all tracked files touched by this feature. Existing unrelated dirty workspace files were left untouched.
- Local Vite server returned HTTP 200 at `/stock/`. No browser screenshot was captured because the available Node browser runtime failed to load its Playwright entry point.
