import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

import { SmallCapAbsorptionPanel } from "./SmallCapAbsorptionPanel";

afterEach(cleanup);

const freshSource = [{ source_id: "small_cap_absorption", source_name: "小市值倍量吸筹",
  status: "ok" as const, generated_at: "2026-09-09T16:00:00+08:00", error: null }];

test("defaults to or-qualified entries and retains noneligible setups for observation", () => {
  const waiting = stagedCandidate(false);
  waiting.stock = { ...waiting.stock, symbol: "600002", name: "待确认样本" };
  render(<SmallCapAbsorptionPanel items={[waiting, stagedCandidate(true)]} sources={freshSource}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  expect(screen.getAllByRole("article")).toHaveLength(1);
  expect(screen.getAllByRole("article")[0]).toHaveTextContent("600001");
  fireEvent.click(screen.getByRole("tab", { name: "观察池 1" }));
  expect(screen.getAllByRole("article")[0]).toHaveTextContent("600002");
  fireEvent.click(screen.getByRole("tab", { name: "全部 2" }));
  expect(screen.getAllByRole("article")).toHaveLength(2);
});

function stagedCandidate(alert: boolean) {
  return {
    ...candidate,
    sources: [{ ...candidate.sources[0], reasons: ["试盘后进入观察池"], factors: {
      rule_version: 4, stage: alert ? "second_volume" : "pullback", alert_active: alert,
      shortlist_qualified: true, entry_gate_version: 3, entry_eligible: alert, entry_basis: alert ? "both" : "none",
      entry_gate_reason: alert ? "板块联动与热门题材均命中" : "等待有效放量确认",
      probe_date: "2026-09-03", confirmation_date: alert ? "2026-09-09" : "",
      trigger_date: alert ? "2026-09-09" : "2026-09-03", as_of_date: "2026-09-09",
      volume_vs_previous: 2.467, volume_vs_ma5: 1.586, max_drawdown_pct: 2.8,
      market_cap_yuan: 9e9, board_stage: "首板形态", confirmation_board_stage: "已封板形态",
    } }],
  };
}

test("shows probe date and pullback stage without an alert before confirmation", () => {
  render(<SmallCapAbsorptionPanel items={[stagedCandidate(false)]} sources={[]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));
  expect(screen.getByText("缩量守位")).toBeInTheDocument();
  expect(screen.getByText("试盘日期")).toBeInTheDocument();
  expect(screen.getByText("2026-09-03")).toBeInTheDocument();
  expect(screen.queryByText("特别提示 · 再次放量")).not.toBeInTheDocument();
});

test("highlights and prioritizes second-volume confirmation with separate volume baselines", () => {
  const watching = { ...candidate, stock: { ...candidate.stock, symbol: "600002", name: "观察样本" } };
  render(<SmallCapAbsorptionPanel items={[watching, stagedCandidate(true)]} sources={[]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));
  expect(screen.getByText("特别提示 · 再次放量")).toBeInTheDocument();
  expect(screen.getAllByText("再次放量日期")).toHaveLength(2);
  expect(screen.getAllByText("确认时封板形态")).toHaveLength(2);
  expect(screen.getByText("已封板形态")).toBeInTheDocument();
  expect(screen.getAllByText("依据")).toHaveLength(2);
  expect(screen.queryByText("确认日 / 昨量")).not.toBeInTheDocument();
  expect(screen.getAllByRole("article")[0]).toHaveTextContent("600001");
});

test("sorts current sealed boards ahead of unsealed candidates", () => {
  const sealed = stagedCandidate(false);
  const unsealed = stagedCandidate(true);
  unsealed.stock = { ...unsealed.stock, symbol: "600002", name: "未封板样本" };
  unsealed.sources = [{
    ...unsealed.sources[0],
    factors: { ...unsealed.sources[0].factors, board_stage: "未封板" },
  }];

  render(<SmallCapAbsorptionPanel items={[unsealed, sealed]} sources={[]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));

  const cards = screen.getAllByRole("article");
  expect(cards[0]).toHaveTextContent("600001");
  expect(cards[1]).toHaveTextContent("600002");
});

test("supports sorting by probe date and confirmation date", () => {
  const older = stagedCandidate(false);
  older.stock = { ...older.stock, symbol: "600001", name: "较早样本" };
  older.sources = [{
    ...older.sources[0],
    factors: { ...older.sources[0].factors, probe_date: "2026-09-03", confirmation_date: "2026-09-09" },
  }];
  const newer = stagedCandidate(false);
  newer.stock = { ...newer.stock, symbol: "600002", name: "较新样本" };
  newer.sources = [{
    ...newer.sources[0],
    factors: { ...newer.sources[0].factors, probe_date: "2026-09-12", confirmation_date: "2026-09-15" },
  }];

  render(<SmallCapAbsorptionPanel items={[older, newer]} sources={[]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));

  const sort = screen.getByRole("combobox", { name: "小市值候选排序" });
  fireEvent.change(sort, { target: { value: "probe_date" } });
  expect(screen.getAllByRole("article")[0]).toHaveTextContent("600002");
  fireEvent.change(sort, { target: { value: "confirmation_date" } });
  expect(screen.getAllByRole("article")[0]).toHaveTextContent("600002");
});

test("labels a retained stale confirmation as historical", () => {
  render(<SmallCapAbsorptionPanel items={[stagedCandidate(true)]}
    sources={[{source_id: "small_cap_absorption", source_name: "小市值倍量吸筹",
      status: "stale", generated_at: "2026-09-09T16:00:00+08:00", error: "行情失败"}]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));
  expect(screen.getByText("历史提示 · 再次放量")).toBeInTheDocument();
  expect(screen.queryByText("特别提示 · 再次放量")).not.toBeInTheDocument();
});

test("active volume confirmation without hot-sector qualification stays in observation", () => {
  const observed = stagedCandidate(true);
  observed.sources[0].factors.entry_eligible = false;
  observed.sources[0].factors.entry_gate_reason = "同期热门题材证据待补";
  render(<SmallCapAbsorptionPanel items={[observed]} sources={freshSource}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  expect(screen.getByRole("tab", { name: "入场候选 0" })).toHaveAttribute("aria-selected", "true");
  expect(screen.queryByRole("article")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("tab", { name: "观察池 1" }));
  expect(screen.getByText("特别提示 · 再次放量")).toBeInTheDocument();
  expect(screen.getByText("同期热门题材证据待补")).toBeInTheDocument();
});

test("stale and legacy caches cannot populate the entry pool", () => {
  const qualified = stagedCandidate(true);
  const view = render(<SmallCapAbsorptionPanel items={[qualified]} sources={[{ ...freshSource[0], status: "stale" }]}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  expect(screen.getByRole("tab", { name: "入场候选 0" })).toBeInTheDocument();
  view.rerender(<SmallCapAbsorptionPanel items={[candidate]} sources={freshSource}
    refreshing={false} onRefresh={vi.fn()} onOpenDetail={vi.fn()} />);
  expect(screen.getByRole("tab", { name: "入场候选 0" })).toBeInTheDocument();
});

const candidate = {
  stock: { symbol: "600001", name: "小市值样本", exchange: "SSE" },
  sources: [
    {
      source_id: "small_cap_absorption",
      source_name: "小市值倍量吸筹",
      score: null,
      reasons: ["首日倍量"],
      factors: {
        market_cap_yuan: 9_000_000_000,
        trigger_date: "2026-08-27",
        volume_multiple: 2.4,
        price_range_pct: 12,
        max_drawdown_pct: 8,
        first_volume_spike: true,
      },
    },
  ],
  generated_at: "2026-08-29T09:00:00+08:00",
};

test("renders the compact absorption summary and reasons", () => {
  render(
    <SmallCapAbsorptionPanel
      items={[candidate]}
      sources={[
        {
          source_id: "small_cap_absorption",
          source_name: "小市值倍量吸筹",
          status: "ok",
          generated_at: "2026-08-29T09:00:00+08:00",
          error: null,
        },
      ]}
      onOpenDetail={vi.fn()}
      onRefresh={vi.fn()}
      refreshing={false}
    />,
  );

  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));

  expect(screen.getByText("小市值倍量吸筹")).toBeInTheDocument();
  expect(screen.getAllByText("首日倍量")).toHaveLength(2);
  expect(screen.getByText("试盘日期")).toBeInTheDocument();
  expect(screen.getByText("2026-08-27")).toBeInTheDocument();
  expect(screen.getByText("再次放量日期")).toBeInTheDocument();
  expect(screen.getByText("确认时封板形态")).toBeInTheDocument();
  expect(screen.getByText("依据")).toBeInTheDocument();
  expect(screen.queryByText("总市值")).not.toBeInTheDocument();
  expect(screen.queryByText("30日区间")).not.toBeInTheDocument();
});

test("opens the shared research detail from an absorption candidate", () => {
  const onOpenDetail = vi.fn();

  render(
    <SmallCapAbsorptionPanel
      items={[candidate]}
      sources={[]}
      onOpenDetail={onOpenDetail}
      onRefresh={vi.fn()}
      refreshing={false}
    />,
  );

  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));

  fireEvent.click(screen.getByRole("button", { name: /600001/ }));

  expect(onOpenDetail).toHaveBeenCalledWith("600001", expect.any(HTMLElement));
});

test("shows stale status while retaining the previous absorption candidates", () => {
  render(
    <SmallCapAbsorptionPanel
      items={[candidate]}
      sources={[
        {
          source_id: "small_cap_absorption",
          source_name: "小市值倍量吸筹",
          status: "stale",
          generated_at: "2026-08-28T09:00:00+08:00",
          error: "市值接口失败",
        },
      ]}
      onOpenDetail={vi.fn()}
      onRefresh={vi.fn()}
      refreshing={false}
    />,
  );

  fireEvent.click(screen.getByRole("tab", { name: /全部/ }));

  expect(screen.getByText(/沿用上一份小市值快照/)).toBeInTheDocument();
  expect(screen.getByText("小市值样本")).toBeInTheDocument();
});
