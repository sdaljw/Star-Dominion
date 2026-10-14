# Small-Cap Shortlist Implementation Plan

**Goal:** Reduce the production small-cap pool to controlled, contracted probe setups and fresh recovery signals.

**Architecture:** Preserve V3 tracking for read-only morphology analysis, use a quality-qualified anchor in V4, then apply causal shortlist gates. Keep the snapshot adapter and existing mainline tags; add explainable factor fields without changing other strategies.

**Tech Stack:** Python/Pydantic/pytest, React/TypeScript/Vitest, SQLite.

1. Add tests in backend/tests/test_small_cap_shortlist.py for qualified and rejected patterns, boundaries and prefix invariance. Run and observe expected failures before implementation.
2. Refactor backend/app/domain/small_cap_probe.py into track_probe plus production evaluate_probe; implement the thresholds from the design. Keep legacy state-machine coverage targeted at track_probe, update adapter fixture to actual contraction.
3. Update workers/analyze_small_cap_shortlist.py to compare V3 tracking and V4 production on the same snapshot and pre-first-board prefixes. Record current counts, subgroup retention and data caveats in a research report.
4. Add frontend/src/components/SmallCapFactors.test.tsx, verify failing V4 rendering, implement V2+ factor rendering and V4 contraction evidence. Run related UI tests and the TypeScript/Vite build.
5. Run the domain, adapter and refresh regressions. Recompute only small_cap_absorption in existing configured candidate databases, preserving source generation dates. Verify cache counts, diff whitespace, and final scope.
6. Add date-bound probe/confirmation sector context from successful historical snapshots; test no look-ahead, peer deduplication, signal-day membership and corrupt-history isolation. Render cycle/ladder badges plus supporting evidence without changing eligibility or scores; leave missing history explicitly unknown.

No commits or additional user approval gates are required.
