import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, test } from "vitest";

import { ProbeSectorTags, SmallCapFactors, smallCapStage, smallCapEntryEligible } from "./SmallCapFactors";

afterEach(cleanup);

test("rejects cached eligibility from before the acquisition-time fixes", () => {
  expect(smallCapEntryEligible({ rule_version: 4, entry_gate_version: 1, shortlist_qualified: true,
    alert_active: true, entry_eligible: true })).toBe(false);
  expect(smallCapEntryEligible({ rule_version: 4, entry_gate_version: 2, shortlist_qualified: true,
    alert_active: true, entry_eligible: true })).toBe(false);
});

test("renders V4 probe and contraction evidence without falling back to legacy fields", () => {
  render(<SmallCapFactors className="factors" factors={{
    rule_version: 4, stage: "pullback", probe_date: "2026-09-21", as_of_date: "2026-09-24",
    volume_vs_previous: 2.5, volume_vs_ma5: 2.2, market_cap_yuan: 5e9,
    max_drawdown_pct: 4.5, consolidation_volume_ratio: .36, probe_age_days: 3,
    probe_gain_pct: 4, gain_since_probe_pct: -2.5, board_stage: "未封板", entry_signal: "待放量确认",
  }} />);
  expect(screen.getByText("2026-09-21")).toBeInTheDocument();
  expect(screen.getByText("2.20 倍")).toBeInTheDocument();
  expect(screen.getByText("36.00%")).toBeInTheDocument();
  expect(screen.getByText("3 个交易日")).toBeInTheDocument();
  expect(screen.getByText("待放量确认")).toBeInTheDocument();
  expect(screen.queryByText("30日区间")).not.toBeInTheDocument();
  expect(smallCapStage({ rule_version: 4, stage: "pullback" })).toBe("缩量守位");
});

test("renders existing V3 factors using the modern field names", () => {
  render(<SmallCapFactors className="factors" factors={{
    rule_version: 3, probe_date: "2026-09-21", volume_vs_ma5: 2.2,
  }} />);
  expect(screen.getByText("2026-09-21")).toBeInTheDocument();
  expect(screen.getByText("2.20 倍")).toBeInTheDocument();
});

test("marks a point-in-time sector cycle and its peer ladder separately from current mainline tags", () => {
  render(<ProbeSectorTags factors={{ probe_sector_status: "confirmed", probe_sector_name: "医药",
    probe_sector_cycle_confirmed: true, probe_sector_ladder_confirmed: true,
    probe_sector_date: "2026-09-10", probe_sector_cycle_days: 3, probe_sector_peer_limitups: 2,
    probe_sector_breadth_pct: 70, probe_sector_peers: "同行甲1板、同行乙2板",
  }} />);
  expect(screen.getByText("试盘时 · 医药周期 · 梯队")).toBeInTheDocument();
  expect(screen.getByText("试盘时 · 医药周期 · 梯队")).toHaveAttribute("title", expect.stringContaining("2026-09-10"));
});

test("does not invent sector support when dated membership is missing", () => {
  render(<ProbeSectorTags factors={{ probe_sector_status: "unavailable" }} />);
  expect(screen.getByText("板块效应待确认")).toBeInTheDocument();
  expect(screen.queryByText(/医药/)).not.toBeInTheDocument();
});

test("shows the qualifying hot theme with its actual ranking proxy and date", () => {
  render(<SmallCapFactors className="factors" factors={{ rule_version: 4,
    entry_eligible: true, entry_gate_version: 3, entry_basis: "both", shortlist_qualified: true, alert_active: true,
    confirmation_hot_theme_status: "confirmed", confirmation_hot_theme_name: "热门测试题材",
    confirmation_hot_theme_rank: 3, confirmation_hot_theme_date: "2026-09-10",
    confirmation_hot_theme_basis: "concept_gain_rank",
  }} />);
  expect(screen.getByText("热门测试题材 · 概念涨幅第3")).toBeInTheDocument();
  expect(screen.getByText("热门题材证据日")).toBeInTheDocument();
  expect(screen.getByText("2026-09-10")).toBeInTheDocument();
  expect(screen.getByText("板块联动与热门题材均命中")).toBeInTheDocument();
});

test("shows hot-only qualification without claiming sector linkage", () => {
  render(<SmallCapFactors className="factors" factors={{ rule_version: 4,
    entry_eligible: true, entry_gate_version: 3, entry_basis: "hot_theme_only", shortlist_qualified: true, alert_active: true,
    confirmation_sector_status: "not_confirmed", confirmation_hot_theme_status: "confirmed",
    confirmation_hot_theme_name: "独立热门题材", confirmation_hot_theme_rank: 20,
    confirmation_hot_theme_date: "2026-09-10", confirmation_hot_theme_sector_confirmed: false,
  }} />);
  expect(screen.getByText("仅同期热门题材前20")).toBeInTheDocument();
  expect(screen.getByText("未达联动标准")).toBeInTheDocument();
  expect(screen.getByText("独立热门题材 · 概念涨幅第20")).toBeInTheDocument();
});

test("shows sector-only qualification and the actual component metrics", () => {
  render(<SmallCapFactors className="factors" factors={{ rule_version: 4,
    entry_eligible: true, entry_gate_version: 3, entry_basis: "sector_only", shortlist_qualified: true, alert_active: true,
    confirmation_sector_status: "confirmed", confirmation_sector_name: "联动题材",
    confirmation_sector_pct: 1.2, confirmation_sector_breadth_pct: 65, confirmation_sector_peer_limitups: 2,
    confirmation_sector_date: "2026-09-10", confirmation_sector_cycle_days: 1, confirmation_sector_peers: "同行甲1板、同行乙1板",
    confirmation_hot_theme_status: "unavailable",
  }} />);
  expect(screen.getByText("仅同期板块联动")).toBeInTheDocument();
  expect(screen.getByText("1.20%")).toBeInTheDocument();
  expect(screen.getByText("65.00%")).toBeInTheDocument();
  expect(screen.getByText("2 只")).toBeInTheDocument();
});
