type Factors = Record<string, number | boolean | string>;

export function smallCapEntryEligible(factors: Factors): boolean {
  return factors.rule_version === 4 && factors.entry_gate_version === 3
    && factors.shortlist_qualified === true && factors.alert_active === true && factors.entry_eligible === true;
}

function entryStatus(factors: Factors): string {
  if (factors.entry_gate_version !== 3) return "入场资格待核";
  const labels: Record<string, string> = {
    both: "板块联动与热门题材均命中", sector_only: "仅同期板块联动", hot_theme_only: "仅同期热门题材前20",
  };
  return smallCapEntryEligible(factors) ? labels[String(factors.entry_basis)] ?? "入场依据待核"
    : typeof factors.entry_gate_reason === "string" ? factors.entry_gate_reason : "入场资格待核";
}

export function smallCapStage(factors: Factors): string {
  if (factors.rule_version === 4 && factors.stage === "pullback") return "缩量守位";
  const stages: Record<string, string> = {
    probe: "试盘观察", pullback: "回落跟踪", second_volume: "再次放量", tracking: "启动后跟踪",
  };
  return stages[String(factors.stage)] ?? (factors.first_volume_spike ? "首日倍量" : "");
}

export function SmallCapFactors({ factors, className }: { factors: Factors; className: string }) {
  const modern = typeof factors.rule_version === "number" && factors.rule_version >= 2;
  const multiple = (v: unknown) => typeof v === "number" ? `${v.toFixed(2)} 倍` : "—";
  const percent = (v: unknown) => typeof v === "number" ? `${v.toFixed(2)}%` : "—";
  const text = (v: unknown) => typeof v === "string" && v ? v : "—";
  return (
    <dl className={className}>
      <Factor label="总市值" value={typeof factors.market_cap_yuan === "number" ? `${(factors.market_cap_yuan / 1e8).toFixed(2)} 亿元` : "—"} />
      {modern ? <>
        <Factor label="试盘日期" value={text(factors.probe_date)} />
        <Factor label="再次放量日期" value={text(factors.confirmation_date)} />
        <Factor label="截至交易日" value={text(factors.as_of_date)} />
        <Factor label={factors.confirmation_date ? "确认日 / 昨量" : "试盘日 / 昨量"} value={multiple(factors.volume_vs_previous)} />
        <Factor label={factors.confirmation_date ? "确认日 / 前5日均量" : "试盘日 / 前5日均量"} value={multiple(factors.volume_vs_ma5)} />
        <Factor label="当前封板形态" value={text(factors.board_stage)} />
        {Boolean(factors.confirmation_date) && <Factor label="确认时封板形态" value={text(factors.confirmation_board_stage)} />}
      </> : <>
        <Factor label="触发日期" value={text(factors.trigger_date)} />
        <Factor label="倍量" value={multiple(factors.volume_multiple)} />
        <Factor label="30日区间" value={percent(factors.price_range_pct)} />
      </>}
      <Factor label="最大回撤" value={percent(factors.max_drawdown_pct)} />
      {factors.rule_version === 4 && <>
        <Factor label="信号" value={text(factors.entry_signal)} />
        <Factor label="试盘涨幅" value={percent(factors.probe_gain_pct)} />
        <Factor label="整理均量 / 试盘量" value={typeof factors.consolidation_volume_ratio === "number" ? percent(factors.consolidation_volume_ratio * 100) : "—"} />
        <Factor label="试盘后" value={typeof factors.probe_age_days === "number" ? `${factors.probe_age_days} 个交易日` : "—"} />
        <Factor label="当前距试盘涨幅" value={percent(factors.gain_since_probe_pct)} />
      </>}
      <SectorFactors factors={factors} prefix="probe" label="试盘时" />
      <SectorFactors factors={factors} prefix="confirmation" label="再放量时" />
      <Factor label="入场资格" value={entryStatus(factors)} />
      <HotThemeFactors factors={factors} />
    </dl>
  );
}

export function ProbeSectorTags({ factors }: { factors: Factors }) {
  const phases = [{ prefix: "probe", label: "试盘时" }, { prefix: "confirmation", label: "再放量时" }];
  const confirmed = phases.filter(({ prefix }) => factors[`${prefix}_sector_status`] === "confirmed");
  if (!confirmed.length) {
    return factors.probe_sector_status ? <span className="probe-sector-pending">板块效应待确认</span> : null;
  }
  return <div className="probe-sector-tags" aria-label="放量时板块效应">
    {confirmed.map(({ prefix, label }) => {
      const key = `${prefix}_sector_`;
      const cycle = factors[key + "cycle_confirmed"] === true;
      const ladder = factors[key + "ladder_confirmed"] === true;
      const title = `${factors[key + "date"]}，小市值主板同行${factors[key + "peer_limitups"]}只涨停，上涨广度${factors[key + "breadth_pct"]}%，近5交易日联动${factors[key + "cycle_days"]}天；${factors[key + "peers"]}`;
      return <span className={`probe-sector-tag${ladder ? " probe-sector-tag--ladder" : ""}`} key={prefix} title={title}>
        {label} · {factors[key + "name"]}{cycle ? "周期" : "联动"}{ladder ? " · 梯队" : ""}
      </span>;
    })}
  </div>;
}

function SectorFactors({ factors, prefix, label }: { factors: Factors; prefix: string; label: string }) {
  const key = `${prefix}_sector_`;
  if (!factors[key + "status"]) return null;
  if (factors[key + "status"] !== "confirmed") return <Factor label={`${label}板块效应`}
    value={factors[key + "status"] === "not_confirmed" ? "未达联动标准" : "证据待补"} />;
  const percent = (value: unknown) => typeof value === "number" ? `${value.toFixed(2)}%` : "—";
  return <>
    <Factor label={`${label}板块效应`} value={`${factors[key + "name"]} · ${factors[key + "cycle_confirmed"] === true ? "周期内" : "当日联动"}`} />
    <Factor label="板块证据日期" value={String(factors[key + "date"])} />
    <Factor label="板块涨幅" value={percent(factors[key + "pct"])} />
    <Factor label="上涨广度" value={percent(factors[key + "breadth_pct"])} />
    <Factor label="其他同行涨停" value={typeof factors[key + "peer_limitups"] === "number" ? `${factors[key + "peer_limitups"]} 只` : "—"} />
    <Factor label="联动证据区间" value={`${factors[key + "evidence_start"] ?? factors[key + "date"]} 至 ${factors[key + "date"]}`} />
    <Factor label="五日内联动" value={`${factors[key + "cycle_days"]} 个交易日`} />
    <Factor label="同期同行梯队" value={String(factors[key + "peers"])} />
  </>;
}

function HotThemeFactors({ factors }: { factors: Factors }) {
  if (!factors.confirmation_hot_theme_status) return null;
  if (factors.confirmation_hot_theme_status !== "confirmed") {
    return <Factor label="同期热门题材" value={factors.confirmation_hot_theme_status === "unavailable" ? "证据待补" : "未确认"} />;
  }
  return <>
    <Factor label="同期热门题材" value={`${factors.confirmation_hot_theme_name} · 概念涨幅第${factors.confirmation_hot_theme_rank}`} />
    <Factor label="热门题材证据日" value={String(factors.confirmation_hot_theme_date)} />
  </>;
}

export function SmallCapSummaryFactors({ factors, className }: { factors: Factors; className: string }) {
  const text = (v: unknown) => typeof v === "string" && v ? v : "—";
  return (
    <dl className={className}>
      <Factor label="试盘日期" value={text(factors.probe_date ?? factors.trigger_date)} />
      <Factor label="再次放量日期" value={text(factors.confirmation_date)} />
      <Factor label="确认时封板形态" value={text(factors.confirmation_board_stage)} />
      {factors.rule_version === 4 && <Factor label="信号" value={text(factors.entry_signal)} />}
      <Factor label="入场状态" value={entryStatus(factors)} />
      <HotThemeFactors factors={factors} />
    </dl>
  );
}

function Factor({ label, value }: { label: string; value: string }) {
  return <div><dt>{label}</dt><dd>{value}</dd></div>;
}
