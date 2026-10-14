"""Causal daily-bar tracking for the small-cap observation pool."""

from datetime import timedelta
import math

from app.domain.strategies import PriceBar, StockSeries, StrategyResult, SMALL_CAP_MARKET_CAP_LIMIT
from app.domain.stocks import InvalidMainBoardSymbol, normalize_symbol

LOOKBACK = 20
VOLUME_MULTIPLE = 2.0
PULLBACK_MIN = 0.02
CONTRACTION_MAX = 0.75
SUPPORT_TOLERANCE = 0.03
MAX_DRAWDOWN = 0.15
ALERT_TRADE_DAYS = 3
RATIO_EPSILON = 1e-10
RECENT_CALENDAR_DAYS = 30
MAX_CONSECUTIVE_LIMIT_UPS = 3
FIVE_DAY_AMPLITUDE_LIMIT = 0.25
SHORTLIST_MAX_AGE = 12
SHORTLIST_MAX_DRAWDOWN = 0.10
SHORTLIST_CONTRACTION_MAX = 0.65
PROBE_MIN_GAIN_PCT = 2.0
PROBE_MIN_CLOSE_LOCATION = 0.60
SHORTLIST_SUPPORT_RATIO = 0.99
SHORTLIST_MAX_GAIN = 0.06
BOARD_ENTRY_MAX_GAIN = 0.20


def _limit_shape(bar: PriceBar) -> bool:
    # QFQ bars do not carry the exchange's unadjusted upper-limit price.
    return 9.8 <= bar.pct <= 10.2 and math.isclose(bar.close, bar.high, abs_tol=0.011)


def _multiples(bars: list[PriceBar], index: int) -> tuple[float, float]:
    average = sum(bar.volume for bar in bars[index - 5:index]) / 5
    return bars[index].volume / bars[index - 1].volume, bars[index].volume / average


def _drawdown(bars: list[PriceBar]) -> float:
    peak = bars[0].close
    maximum = 0.0
    for bar in bars:
        maximum = max(maximum, 1 - bar.close / peak)
        peak = max(peak, bar.close)
    return maximum


def _recent_activity_risk(bars: list[PriceBar]) -> str | None:
    if not bars or bars[-1].date is None:
        return None
    cutoff = bars[-1].date - timedelta(days=RECENT_CALENDAR_DAYS)
    start = next((i for i, bar in enumerate(bars) if bar.date and bar.date >= cutoff), len(bars))
    recent = bars[start:]

    consecutive = 0
    for bar in recent:
        consecutive = consecutive + 1 if _limit_shape(bar) else 0
        if consecutive >= MAX_CONSECUTIVE_LIMIT_UPS:
            return "近30天出现连续3板及以上"

    for end in range(max(start + 4, 4), len(bars)):
        prior_close = bars[end - 5].close
        window = bars[end - 4:end + 1]
        if prior_close > 0:
            amplitude = (max(bar.high for bar in window) - min(bar.low for bar in window)) / prior_close
            if amplitude + RATIO_EPSILON >= FIVE_DAY_AMPLITUDE_LIMIT:
                return "近30天出现5日累计振幅达到25%"
    return None


def _quality_probe(bars: list[PriceBar], index: int) -> bool:
    bar = bars[index]
    spread = bar.high - bar.low
    location = (bar.close - bar.low) / spread if spread > 0 else 1.0
    _, mean_multiple = _multiples(bars, index)
    return (mean_multiple + RATIO_EPSILON >= VOLUME_MULTIPLE
            and bar.pct + RATIO_EPSILON >= PROBE_MIN_GAIN_PCT
            and location + RATIO_EPSILON >= PROBE_MIN_CLOSE_LOCATION)


def track_probe(stock: StockSeries, *, require_quality: bool = False) -> StrategyResult:
    """Track the wider morphology pool; production selection uses evaluate_probe."""
    result = StrategyResult(strategy_id="small_cap_absorption", strategy_name="小市值倍量吸筹",
                            matched=False, score=0)
    try:
        normalize_symbol(stock.symbol)
    except InvalidMainBoardSymbol:
        result.risk_flags.append("非 A 股主板")
        return result
    if "ST" in stock.name.upper() or "退" in stock.name:
        result.risk_flags.append("ST 或退市股票不进入候选池")
        return result
    cap = stock.market_cap
    if cap is None or not math.isfinite(cap) or cap <= 0:
        result.risk_flags.append("缺少有效总市值")
        return result
    if cap >= SMALL_CAP_MARKET_CAP_LIMIT:
        result.risk_flags.append("总市值不低于 100 亿元")
        return result
    recent_risk = _recent_activity_risk(stock.bars)
    if recent_risk:
        result.risk_flags.append(recent_risk)
        return result
    bars = stock.bars[-(LOOKBACK + 5):]
    if len(bars) < 6:
        result.risk_flags.append("K 线少于 6 个交易日，无法计算前 5 日均量")
        return result
    for i, bar in enumerate(bars):
        numbers = (bar.open, bar.high, bar.low, bar.close, bar.volume, bar.pct)
        if (bar.date is None or not all(math.isfinite(v) for v in numbers)
                or min(numbers[:-1]) <= 0
                or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
                or (i > 0 and bar.date <= bars[i - 1].date)):
            result.risk_flags.append("日线日期、价格或成交量无效")
            return result

    probe: int | None = None
    confirmation: int | None = None
    peak_close = 0.0
    max_drawdown = 0.0
    pulled_back = False
    for i in range(5, len(bars)):
        bar = bars[i]
        previous_multiple, mean_multiple = _multiples(bars, i)
        doubled = max(previous_multiple, mean_multiple) >= VOLUME_MULTIPLE
        rising = bar.close >= bar.open and bar.close > bars[i - 1].close
        if require_quality and probe is not None and i - probe > SHORTLIST_MAX_AGE:
            probe = confirmation = None
        if probe is None:
            if (rising and (doubled or _limit_shape(bar))
                    and (not require_quality or _quality_probe(bars, i))):
                probe = i
                peak_close = bar.close
                max_drawdown = 0.0
                pulled_back = False
            continue

        drawdown = max(0.0, 1 - bar.close / peak_close)
        if (bar.close < bars[probe].low * (1 - SUPPORT_TOLERANCE)
                or drawdown > MAX_DRAWDOWN + RATIO_EPSILON):
            probe = confirmation = None
            continue
        # All consolidation evidence ends yesterday. Today's volume/price cannot
        # create its own pullback or its own low-volume baseline.
        anchor = confirmation if confirmation is not None else probe
        middle = bars[anchor + 1:i]
        if len(middle) >= 2 and _drawdown(bars[anchor:i]) + RATIO_EPSILON >= PULLBACK_MIN:
            prior_peak_volume = max(b.volume for b in bars[anchor:i - 2])
            contracted = sum(b.volume for b in middle[-2:]) / 2 <= prior_peak_volume * CONTRACTION_MAX
            recovered = rising and bar.close > max(b.close for b in middle[-2:])
            if contracted and recovered and doubled:
                probe = anchor
                confirmation = i
                max_drawdown = _drawdown(bars[probe:i + 1])
                peak_close = max(b.close for b in bars[probe:i + 1])
        max_drawdown = max(max_drawdown, drawdown)
        pulled_back = pulled_back or drawdown + RATIO_EPSILON >= PULLBACK_MIN
        peak_close = max(peak_close, bar.close)

    if probe is None:
        return result
    result.matched = True
    signal_index = confirmation if confirmation is not None else probe
    previous_multiple, mean_multiple = _multiples(bars, signal_index)
    probe_previous, probe_mean = _multiples(bars, probe)
    alert = confirmation is not None and len(bars) - 1 - confirmation < ALERT_TRADE_DAYS
    stage = ("second_volume" if alert else "tracking") if confirmation is not None else (
        "pullback" if pulled_back else "probe")
    consecutive = 0
    for bar in reversed(bars):
        if not _limit_shape(bar):
            break
        consecutive += 1
    board_stage = "未封板" if not consecutive else (
        "首板形态" if consecutive == 1 else f"{consecutive}连板形态")
    result.factors = {
        "rule_version": 3,
        "stage": stage,
        "alert_active": alert,
        "market_cap_yuan": round(cap, 2),
        "probe_date": bars[probe].date.isoformat(),
        "probe_kind": "涨停形态" if _limit_shape(bars[probe]) else "放量试盘",
        "probe_volume_vs_previous": round(probe_previous, 4),
        "probe_volume_vs_ma5": round(probe_mean, 4),
        "trigger_date": bars[signal_index].date.isoformat(),
        "as_of_date": bars[-1].date.isoformat(),
        "volume_vs_previous": round(previous_multiple, 4),
        "volume_vs_ma5": round(mean_multiple, 4),
        "max_drawdown_pct": round(max_drawdown * 100, 4),
        "probe_age_days": len(bars) - 1 - probe,
        "board_stage": board_stage,
    }
    result.reasons = ["试盘后进入观察池", "日线收盘确认，最多跟踪 20 个交易日"]
    if pulled_back:
        result.reasons.append("试盘后已出现价格回落")
    if confirmation is not None:
        result.factors["confirmation_date"] = bars[confirmation].date.isoformat()
        result.factors["confirmation_age_days"] = len(bars) - 1 - confirmation
        result.factors["confirmation_board_stage"] = (
            "已封板形态" if _limit_shape(bars[confirmation]) else "未封板")
        result.reasons.append("整理缩量后价格转强，再次达到倍量")
    return result


def evaluate_probe(stock: StockSeries) -> StrategyResult:
    result = track_probe(stock, require_quality=True)
    result.factors["rule_version"] = 4
    result.factors["shortlist_qualified"] = False
    if not result.matched:
        return result

    bars = stock.bars[-(LOOKBACK + 5):]
    probe_index = next(i for i, b in enumerate(bars)
                       if b.date.isoformat() == result.factors["probe_date"])
    probe = bars[probe_index]
    confirmation_date = result.factors.get("confirmation_date")
    confirmation_index = next((i for i, b in enumerate(bars)
                               if b.date.isoformat() == confirmation_date), None)
    # Confirmation-day volume must never supply its own contraction evidence.
    end = confirmation_index if confirmation_index is not None else len(bars)
    consolidation = bars[probe_index + 1:end]
    contraction = (sum(b.volume for b in consolidation[-2:]) / 2 / probe.volume
                   if len(consolidation) >= 2 else None)
    drawdown = _drawdown(bars[probe_index:])
    gain = bars[-1].close / probe.close - 1
    spread = probe.high - probe.low
    location = (probe.close - probe.low) / spread if spread > 0 else 1.0
    board_entry = (result.factors["alert_active"] and _limit_shape(bars[-1])
                   and result.factors["board_stage"] in ("首板形态", "2连板形态"))
    entry_signal = ("首板确认" if result.factors["board_stage"] == "首板形态" else "二板确认") if board_entry else (
        "放量转强" if result.factors["alert_active"] else "待放量确认")
    result.factors.update({
        "probe_gain_pct": round(probe.pct, 4),
        "probe_close_location_pct": round(location * 100, 4),
        "gain_since_probe_pct": round(gain * 100, 4),
        "max_drawdown_pct": round(drawdown * 100, 4),
        "entry_signal": entry_signal,
    })
    if contraction is not None:
        result.factors["consolidation_volume_ratio"] = round(contraction, 4)

    rejection = None
    age = len(bars) - 1 - probe_index
    if not _quality_probe(bars, probe_index):
        rejection = "试盘未达到均量倍量、涨幅及收盘位置要求"
    elif not 2 <= age <= SHORTLIST_MAX_AGE:
        rejection = "试盘后未整理两日或已超过12个交易日"
    elif drawdown > SHORTLIST_MAX_DRAWDOWN + RATIO_EPSILON:
        rejection = "试盘后最大回撤超过10%"
    elif bars[-1].close + RATIO_EPSILON < probe.open * SHORTLIST_SUPPORT_RATIO:
        rejection = "当前收盘未守住试盘开盘价99%"
    elif gain > (BOARD_ENTRY_MAX_GAIN if board_entry else SHORTLIST_MAX_GAIN) + RATIO_EPSILON:
        rejection = "当前距试盘涨幅超过一二板确认20%或普通观察6%的上限"
    elif confirmation_index is not None and not result.factors["alert_active"]:
        rejection = "再次放量提示已过期，不纳入启动后跟踪票"
    elif (contraction is None or contraction > SHORTLIST_CONTRACTION_MAX + RATIO_EPSILON
          or _drawdown(bars[probe_index:end]) + RATIO_EPSILON < PULLBACK_MIN):
        rejection = "未形成至少2%回落及两日均量降至试盘量65%以内"

    if rejection:
        result.matched = False
        result.reasons = []
        result.risk_flags.append(rejection)
    else:
        result.factors["shortlist_qualified"] = True
        result.reasons = ["试盘涨幅至少2%，前5日均量倍量且收盘靠上",
                          "缩量回落守位，试盘后2至12个交易日精筛"]
        if confirmation_index is not None:
            result.reasons.append("此前缩量整理后价格恢复，再次倍量提示有效")
    return result
