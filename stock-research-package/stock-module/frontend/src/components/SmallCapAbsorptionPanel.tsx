import { useState } from "react";

import type { CandidateSource, CandidateSourceStatus, CandidateStock, MarketLineTag } from "../types";
import { ProbeSectorTags, SmallCapSummaryFactors, smallCapStage, smallCapEntryEligible } from "./SmallCapFactors";
import { MarketLineTags } from "./MarketLinePanel";

type Props = {
  items: CandidateStock[];
  sources: CandidateSourceStatus[];
  marketLineTags?: Map<string, MarketLineTag[]>;
  refreshing: boolean;
  onOpenDetail: (symbol: string, trigger?: HTMLElement) => void;
  onRefresh: () => void;
};

const sourceId = "small_cap_absorption";
type SortMode = "board" | "probe_date" | "confirmation_date";
type PoolMode = "entry" | "observation" | "all";

export function SmallCapAbsorptionPanel({
  items,
  sources,
  marketLineTags,
  refreshing,
  onOpenDetail,
  onRefresh,
}: Props) {
  const [sortMode, setSortMode] = useState<SortMode>("board");
  const [poolMode, setPoolMode] = useState<PoolMode>("entry");
  const absorptionItems = items.flatMap((item) => {
    const source = item.sources.find((candidate) => candidate.source_id === sourceId);
    return source ? [{ item, source }] : [];
  }).sort((a, b) => compareAbsorptionItems(a.source, b.source, sortMode));
  const status = sources.find((source) => source.source_id === sourceId);
  const eligible = (source: CandidateSource) => status?.status === "ok" && smallCapEntryEligible(source.factors ?? {});
  const entryCount = absorptionItems.filter(({ source }) => eligible(source)).length;
  const poolTabs: { mode: PoolMode; label: string; count: number }[] = [
    { mode: "entry", label: "入场候选", count: entryCount },
    { mode: "observation", label: "观察池", count: absorptionItems.length - entryCount },
    { mode: "all", label: "全部", count: absorptionItems.length },
  ];
  const visibleItems = absorptionItems.filter(({ source }) => poolMode === "all"
    || eligible(source) === (poolMode === "entry"));

  return (
    <aside className="panel small-cap-panel" aria-labelledby="small-cap-title">
      <div className="panel-heading">
        <div>
          <span className="section-kicker">独立规则池</span>
          <h2 id="small-cap-title">小市值倍量吸筹</h2>
        </div>
        <div className="small-cap-heading-actions">
          <label className="small-cap-sort">
            <span>排序</span>
            <select
              aria-label="小市值候选排序"
              value={sortMode}
              onChange={(event) => setSortMode(event.target.value as SortMode)}
            >
              <option value="board">当前状态（已封板优先）</option>
              <option value="probe_date">试盘日期（新到旧）</option>
              <option value="confirmation_date">再次放量日期（新到旧）</option>
            </select>
          </label>
          <button className="refresh-action absorption" type="button" disabled={refreshing} onClick={onRefresh}>
            {refreshing ? "运行中…" : "运行吸筹"}
          </button>
        </div>
      </div>
      <div className="research-panel-body">
        <div className="small-cap-pool-tabs" role="tablist" aria-label="小市值候选状态">
          {poolTabs.map(({ mode, label, count }, index) => (
            <button key={mode} id={`small-cap-tab-${mode}`} role="tab" type="button"
              aria-selected={poolMode === mode} aria-controls="small-cap-candidates"
              tabIndex={poolMode === mode ? 0 : -1} onClick={() => setPoolMode(mode)}
              onKeyDown={(event) => {
                const target = event.key === "ArrowRight" ? (index + 1) % poolTabs.length
                  : event.key === "ArrowLeft" ? (index + poolTabs.length - 1) % poolTabs.length
                    : event.key === "Home" ? 0 : event.key === "End" ? poolTabs.length - 1 : -1;
                if (target < 0) return;
                event.preventDefault();
                setPoolMode(poolTabs[target].mode);
                document.getElementById(`small-cap-tab-${poolTabs[target].mode}`)?.focus();
              }}>
              {label} <span>{count}</span>
            </button>
          ))}
        </div>
        {status?.status === "stale" && (
          <p className="source-alert source-alert-stale">沿用上一份小市值快照{status.error ? `：${status.error}` : ""}</p>
        )}
        {status?.status === "error" && (
          <p className="source-alert">小市值策略刷新失败{status.error ? `：${status.error}` : ""}</p>
        )}
        {status?.status === "not_configured" && (
          <p className="source-alert">小市值策略尚无可用快照</p>
        )}
        <div className="small-cap-list" id="small-cap-candidates" role="tabpanel" aria-labelledby={`small-cap-tab-${poolMode}`}>
          {visibleItems.map(({ item, source }) => (
            <SmallCapCandidateCard
              key={item.stock.symbol}
              item={item}
              source={source}
              marketLineTags={marketLineTags?.get(item.stock.symbol)}
              onOpenDetail={onOpenDetail}
              stale={status?.status === "stale" || status?.status === "error"}
            />
          ))}
          {visibleItems.length === 0 && (
            <p className="panel-empty">{poolMode === "entry" ? "暂无板块联动或热门题材合格候选。" : "暂未发现符合条件的小市值试盘候选。"}</p>
          )}
        </div>
      </div>
    </aside>
  );
}

function currentBoardPriority(factors?: CandidateSource["factors"]): number {
  const boardStage = factors?.board_stage ?? factors?.confirmation_board_stage;
  return typeof boardStage === "string" && boardStage.length > 0 && boardStage !== "未封板" ? 1 : 0;
}

function compareAbsorptionItems(a: CandidateSource, b: CandidateSource, sortMode: SortMode): number {
  if (sortMode === "probe_date") {
    const dateOrder = compareDateDescending(factorDate(a, "probe_date", "trigger_date"), factorDate(b, "probe_date", "trigger_date"));
    if (dateOrder !== 0) return dateOrder;
  }
  if (sortMode === "confirmation_date") {
    const dateOrder = compareDateDescending(factorDate(a, "confirmation_date"), factorDate(b, "confirmation_date"));
    if (dateOrder !== 0) return dateOrder;
  }
  const boardPriority = currentBoardPriority(b.factors) - currentBoardPriority(a.factors);
  if (boardPriority !== 0) return boardPriority;
  return Number(b.factors?.alert_active === true) - Number(a.factors?.alert_active === true);
}

function factorDate(source: CandidateSource, primary: string, fallback?: string): string {
  const value = source.factors?.[primary];
  if (typeof value === "string" && value) return value;
  const fallbackValue = fallback ? source.factors?.[fallback] : undefined;
  return typeof fallbackValue === "string" ? fallbackValue : "";
}

function compareDateDescending(a: string, b: string): number {
  if (!a && !b) return 0;
  if (!a) return 1;
  if (!b) return -1;
  return b.localeCompare(a);
}

function SmallCapCandidateCard({
  item,
  source,
  marketLineTags,
  onOpenDetail,
  stale,
}: {
  item: CandidateStock;
  source: CandidateSource;
  marketLineTags?: MarketLineTag[];
  onOpenDetail: (symbol: string, trigger?: HTMLElement) => void;
  stale: boolean;
}) {
  const factors = source.factors ?? {};
  const stage = smallCapStage(factors);
  const alert = factors.alert_active === true;

  return (
    <article className={`small-cap-item${alert && !stale ? " small-cap-item-alert" : ""}`}>
      {alert && <p className="small-cap-signal"><strong>{stale ? "历史提示" : "特别提示"} · 再次放量</strong></p>}
      <div className="small-cap-item-title">
        <div><strong>{item.stock.name}</strong><span>{item.stock.symbol}</span></div>
        {stage && <em>{stage}</em>}
      </div>
      <MarketLineTags tags={marketLineTags} />
      <ProbeSectorTags factors={factors} />
      <SmallCapSummaryFactors factors={factors} className="small-cap-factors small-cap-factors--compact" />
      <div className="small-cap-reason">
        <span>依据</span>
        <p>{source.reasons.join(" · ") || "—"}</p>
      </div>
      <button
        type="button"
        aria-label={`查看 ${item.stock.name} ${item.stock.symbol} 详情`}
        onClick={(event) => onOpenDetail(item.stock.symbol, event.currentTarget)}
      >查看依据</button>
    </article>
  );
}
