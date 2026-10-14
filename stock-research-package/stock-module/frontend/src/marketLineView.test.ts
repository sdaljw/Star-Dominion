import { expect, test } from "vitest";

import { mainlineTagsBySymbol } from "./marketLineView";
import type { MarketLineSnapshot } from "./types";

const snapshot: MarketLineSnapshot = {
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
  lines: [
    {
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
      eligible_member_symbols: ["000001", "000003"],
      members: [
        { symbol: "000001", name: "平安银行", pct: 10, consecutive_boards: 1, market_cap_yuan: 5e9 },
      ],
    },
    {
      name: "观察主题",
      code: "301025",
      source_rank: 2,
      score: 40,
      label: "观察",
      rank: 2,
      pct: 0,
      turnover_yi: 10,
      up_count: 20,
      down_count: 80,
      breadth_score: 20,
      persistence_count: 1,
      ladder_score: 0,
      activity_score: 10,
      ladder_tiers: { first_board: 0, second_board: 0, three_plus_board: 0 },
      known_bar_count: 30,
      eligible_small_cap_count: 40,
      eligible_member_symbols: ["600002"],
      members: [
        { symbol: "600002", name: "观察样本", pct: 1, consecutive_boards: 1, market_cap_yuan: 4e9 },
      ],
    },
  ],
};

test("maps only exact member symbols from fresh non-observation themes", () => {
  const tags = mainlineTagsBySymbol(snapshot);

  expect(tags.get("000001")).toEqual([{ name: "机器人", label: "主线候选", rank: 1 }]);
  expect(tags.get("000003")).toEqual([{ name: "机器人", label: "主线候选", rank: 1 }]);
  expect(tags.has("00000")).toBe(false);
  expect(tags.has("600002")).toBe(false);
});

test("does not produce candidate tags from stale or unavailable snapshots", () => {
  expect(mainlineTagsBySymbol({ ...snapshot, status: "stale" }).size).toBe(0);
  expect(mainlineTagsBySymbol(null).size).toBe(0);
});
