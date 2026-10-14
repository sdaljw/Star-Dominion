import type { MarketLineSnapshot, MarketLineTag } from "../types";

type Props = {
  snapshot: MarketLineSnapshot | null;
  error: string;
};

export function MarketLinePanel({ snapshot, error }: Props) {
  const environment = snapshot?.market_environment;
  const statusLabel = snapshot?.status === "fresh"
    ? "当前快照"
    : snapshot?.status === "stale"
      ? "快照已过期"
      : "暂无主线快照";

  return (
    <section className="market-line-panel" aria-labelledby="market-line-title">
      <div className="market-line-heading">
        <div>
          <span className="section-kicker">上证与深市主板</span>
          <h2 id="market-line-title">市场主线（主板）</h2>
        </div>
        <div className="market-line-meta">
          <span className={`market-line-status ${snapshot?.status ?? "unavailable"}`}>{statusLabel}</span>
          {snapshot?.as_of_date && <time dateTime={snapshot.as_of_date}>截至 {snapshot.as_of_date}</time>}
        </div>
      </div>

      {error && <p className="source-alert" role="alert">{error}</p>}
      {snapshot?.status === "stale" && (
        <p className="market-line-notice" role="status">展示最近一次成功快照，候选标签暂不参与判断。</p>
      )}

      <div className="market-line-environment" aria-label="主板市场环境">
        <div className={`market-environment-label ${environment?.label === "偏弱" ? "weak" : environment?.label === "偏强" ? "strong" : "neutral"}`}>
          <span>市场环境</span>
          <strong>{environment?.label ?? "暂无数据"}</strong>
        </div>
        <EnvironmentMetric label="上涨" value={environment?.advancing ?? 0} tone="up" />
        <EnvironmentMetric label="下跌" value={environment?.declining ?? 0} tone="down" />
        <EnvironmentMetric label="平盘" value={environment?.flat ?? 0} />
        <EnvironmentMetric label="涨停" value={environment?.limit_up_count ?? 0} tone="limit" />
      </div>

      {snapshot?.lines.length ? (
        <div className="market-line-list-wrap">
        <div className="market-line-list" aria-label="主线主题排名">
          <div className="market-line-list-head" aria-hidden="true">
            <span>主题 / 得分</span><span>标签</span><span>梯队</span><span>广度 / 延续</span><span>小市值涨停股</span>
          </div>
          {snapshot.lines.map((line) => (
            <article className="market-line-row" key={`${line.code}-${line.name}`}>
              <div className="market-line-theme">
                <span className="market-line-rank">{String(line.rank).padStart(2, "0")}</span>
                <div>
                  <strong>{line.name}</strong>
                  <span>THS #{line.source_rank || "—"} · {line.pct >= 0 ? "+" : ""}{line.pct.toFixed(2)}% · 综合 {line.score.toFixed(1)}</span>
                </div>
              </div>
              <div className="market-line-tag-cell">
                <MarketLineBadge label={line.label} />
                <span className="market-line-score-parts">梯队 {line.ladder_score.toFixed(0)} · 活跃 {line.activity_score.toFixed(0)}</span>
              </div>
              <div className="market-line-ladder">
                <span className="board-tier first">首板 {line.ladder_tiers.first_board ?? 0}</span>
                <span className="board-tier second">二板 {line.ladder_tiers.second_board ?? 0}</span>
                <span className="board-tier high">三板+ {line.ladder_tiers.three_plus_board ?? 0}</span>
              </div>
              <div className="market-line-breadth">
                <strong>{line.breadth_score.toFixed(0)}%</strong>
                <span>延续 {line.persistence_count}/5 · {line.known_bar_count}/{line.eligible_small_cap_count} 有效K线</span>
              </div>
              <div className="market-line-leaders">
                {line.members.slice(0, 4).map((member) => (
                  <span key={member.symbol}>
                    <strong>{member.name}</strong> {member.consecutive_boards}板
                  </span>
                ))}
                {!line.members.length && <span className="market-line-no-leaders">暂无符合口径的涨停股</span>}
                {line.members.length > 4 && <small>另有 {line.members.length - 4} 只</small>}
              </div>
            </article>
          ))}
        </div>
        </div>
      ) : (
        <p className="market-line-empty">{snapshot?.status === "stale" ? "最近快照没有可展示的主题" : "暂无可用的主线主题数据"}</p>
      )}
    </section>
  );
}

export function MarketLineBadge({ label }: { label: MarketLineTag["label"] | "观察" }) {
  const tone = label === "持续主线" ? "persistent" : label === "主线候选" ? "candidate" : label === "快速轮动" ? "rotation" : "watch";
  return <span className={`market-line-badge ${tone}`}>{label}</span>;
}

export function MarketLineTags({ tags }: { tags?: MarketLineTag[] }) {
  if (!tags?.length) return null;
  return (
    <span className="candidate-mainline-tags" aria-label="所属市场主线">
      {tags.map((tag) => (
        <span className={`market-line-badge ${tag.label === "持续主线" ? "persistent" : tag.label === "主线候选" ? "candidate" : "rotation"}`} key={`${tag.rank}-${tag.name}`}>
          {tag.label} · {tag.name}
        </span>
      ))}
    </span>
  );
}

function EnvironmentMetric({ label, value, tone = "" }: { label: string; value: number; tone?: string }) {
  return (
    <div className={`market-environment-metric ${tone}`}>
      <span>{label}</span>
      <strong>{value.toLocaleString("zh-CN")}</strong>
    </div>
  );
}
