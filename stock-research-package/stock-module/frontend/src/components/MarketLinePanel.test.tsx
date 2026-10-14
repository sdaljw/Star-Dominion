import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";

import { MarketLinePanel } from "./MarketLinePanel";
import type { MarketLineSnapshot } from "../types";

const freshSnapshot: MarketLineSnapshot = {
  status: "fresh",
  as_of_date: "2026-09-24",
  generated_at: "2026-09-24T16:00:00+08:00",
  source: "同花顺",
  market_environment: {
    label: "偏强",
    advancing: 700,
    declining: 300,
    flat: 20,
    limit_up_count: 50,
  },
  hot_concept_ranks: { 机器人: 1 },
  lines: [{
    name: "机器人",
    code: "301024",
    source_rank: 1,
    score: 76.5,
    label: "主线候选",
    rank: 1,
    pct: 4.2,
    turnover_yi: 300,
    up_count: 70,
    down_count: 30,
    breadth_score: 70,
    persistence_count: 3,
    ladder_score: 72,
    activity_score: 80,
    ladder_tiers: { first_board: 3, second_board: 1, three_plus_board: 0 },
    known_bar_count: 30,
    eligible_small_cap_count: 40,
    eligible_member_symbols: ["000001"],
    members: [
      { symbol: "000001", name: "平安银行", pct: 10, consecutive_boards: 1, market_cap_yuan: 5e9 },
    ],
  }],
};

test("shows the environment, scored themes, ladder, and actual snapshot date", () => {
  render(<MarketLinePanel snapshot={freshSnapshot} error="" />);

  expect(screen.getByRole("heading", { name: "市场主线（主板）" })).toBeInTheDocument();
  expect(screen.getByText("偏强" )).toBeInTheDocument();
  expect(document.querySelector("time")?.textContent).toContain("2026-09-24");
  expect(screen.getAllByText("机器人").length).toBeGreaterThan(0);
  expect(screen.getByText("主线候选")).toBeInTheDocument();
  expect(screen.getByText("首板 3")).toBeInTheDocument();
  expect(document.querySelector(".market-line-theme")?.textContent).toContain("76.5");
});

test("keeps stale data visible but marks it as old", () => {
  render(<MarketLinePanel snapshot={{ ...freshSnapshot, status: "stale" }} error="" />);

  expect(screen.getByText("快照已过期" )).toBeInTheDocument();
  expect(screen.getAllByText("机器人").length).toBeGreaterThan(0);
});

test("shows a quiet empty state when no market-line data exists", () => {
  render(<MarketLinePanel snapshot={null} error="" />);

  expect(screen.getByText("暂无主线快照")).toBeInTheDocument();
});
