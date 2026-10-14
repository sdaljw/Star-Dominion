# Market Mainline and Candidate Context

## Goal

Add a data-backed market-mainline view to the stock module. It should help distinguish durable sector leadership from short-lived rotation and provide contextual labels for the user's small-cap, volume-expansion candidates. It is observational context, not a buy/sell signal, and it must not alter existing candidate scores, sorting, or filters.

## Scope and presentation

- Add a full-width market-mainline panel between the market overview and strategy panels.
- Show the main-board market environment, the five highest-scoring themes, score components, recent persistence, and the 00/60 small-cap limit-up ladder.
- Add contextual theme labels beside exact-symbol candidate matches in both strategy and small-cap absorption views. Multiple matching themes may be shown; absent or stale data produces no inferred label.
- The panel loads on initial page load and refreshes after a candidate refresh completes successfully or partially.

## Data and scoring

- Use Tonghuashun's hot-concept ranking/detail feed for up to 30 themes. Preserve its rank for each trading date; persistence is based on presence in the source top ten, not the composite ranking.
- Calculate five-session persistence against actual trading dates from the small-cap K-lines. A trading date without a saved source snapshot counts as absent rather than reaching farther back.
- Use the existing Eastmoney full-market quote request to calculate advancing, declining, flat, and limit-up counts for non-ST Shanghai/Shenzhen main-board stocks. Do not add a second quote request.
- For each theme, count its members with fresh daily bars who are main-board 00/60, non-ST/non-delisting, and have positive market cap below CNY 10 billion. Count consecutive limit-up closes ending on the snapshot date; expose first, second, and three-or-more-board tiers and leader members.
- Composite score: 35% limit-up ladder, 25% theme breadth, 25% five-session persistence, and 15% relative theme return/turnover activity. Ladder points are `8*first + 18*second + 28*three_plus + 15*active_tier_count`, capped at 100. Activity is the average percentile rank of theme return and turnover among the fetched themes.
- `持续主线`: composite rank <= 3, top-ten source rank on at least 3 of the latest 5 sessions, theme breadth > 50%, and at least two qualifying small-cap limit-up leaders.
- `主线候选`: rank <= 3, score >= 60, and persistence >= 2, but not already persistent.
- `快速轮动`: rank <= 3, score >= 60, and persistence <= 1. Remaining themes are `观察`.
- The market environment is `偏弱` when advancing share is below 40%, `偏强` at or above 60%, otherwise `中性`; no valid breadth is `暂无数据`.

## Persistence, freshness, and failure behavior

- Keep at most 60 date-keyed daily snapshots adjacent to `latest.json` in `market-line-history.json`. Same-date saves replace that date, history remains sorted, and writes are atomic.
- Append only after 15:00 Asia/Shanghai when the market date matches the latest complete small-cap bar date and both the quote and THS concept sources succeeded. Do not append from partial/stale data.
- Preserve the existing 09:00 candidate refresh. Add a configurable weekday 15:30 refresh (default `STOCK_MARKET_LINE_REFRESH_TIME=15:30`) using the existing refresh queue so a finalized daily snapshot is collected automatically; an empty setting disables this extra refresh.
- Read current snapshot from the history file. Compare it with the latest small-cap bar date and source status in `latest.json`; return `fresh`, `stale`, or `unavailable`. Keep the endpoint HTTP 200 for all three states so the UI can explain missing data without failing the page.
- Source errors must not overwrite the latest successful history. The current small-cap snapshot's existing preservation behavior remains unchanged.

## API and frontend contract

- Add `GET /api/v1/market-line/current` returning status, as-of date, generation time, source, main-board environment, and up to five scored lines.
- A line includes score/rank/label, source breadth/rank persistence, ladder tiers/coverage, and a capped member list with symbol, name, consecutive boards, percentage change, and market cap.
- Add one compact line-tag component/mapping based on exact normalized symbols. A stale/unavailable response remains visible in the market panel but is not used to tag candidates.
- Do not change candidate filtering, ranking, or existing strategy behavior.

## Known limitation

Existing cached K-lines may be newer than the last saved market-line snapshot. The UI must display the actual as-of date and a stale indicator; it must never present stale labels as current.
