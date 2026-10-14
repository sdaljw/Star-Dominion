"""Causal daily-bar replay of the user's dip-entry, board-aware exit policy."""

from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
import math

from app.domain.small_cap_probe import _limit_shape
from app.domain.strategies import StockSeries


@dataclass(frozen=True)
class TradePolicy:
    dip_pct: float = .01
    entry_sessions: int = 3
    max_holding_sessions: int = 30
    buy_fee_rate: float = .001
    sell_fee_rate: float = .001
    slippage_rate: float = .0005
    stop_loss_pct: float | None = .07

    def __post_init__(self):
        for value in (self.dip_pct, self.buy_fee_rate, self.sell_fee_rate, self.slippage_rate):
            if not math.isfinite(value) or not 0 <= value < 1:
                raise ValueError("Policy rates must be finite and between zero and one")
        for value in (self.entry_sessions, self.max_holding_sessions):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError("Session counts must be positive integers")
        if self.stop_loss_pct is not None and (
                not math.isfinite(self.stop_loss_pct) or not 0 < self.stop_loss_pct < 1):
            raise ValueError("Stop-loss fraction must be between zero and one, or None")

    @property
    def maturity_sessions(self) -> int:
        return self.entry_sessions + self.max_holding_sessions


@dataclass
class TradeReplay:
    status: str
    signal_index: int
    limit_price: float
    reserved_until_index: int
    entry_index: int | None = None
    entry_price: float | None = None
    entry_fill_price: float | None = None
    exit_index: int | None = None
    exit_price: float | None = None
    exit_fill_price: float | None = None
    exit_timing: str | None = None
    exit_reason: str | None = None
    pending_exit_reason: str | None = None
    holding_sessions: int = 0
    max_owned_board_streak: int = 0
    blocked_exit_sessions: int = 0
    profit_orders_cancelled: int = 0
    net_return_pct: float | None = None
    mark_return_pct: float | None = None
    worst_close_return_pct: float | None = None
    stop_trigger_price: float | None = None
    stop_trigger_index: int | None = None


def _net_return(price: float, entry_fill: float, policy: TradePolicy) -> float:
    proceeds = price * (1 - policy.slippage_rate) * (1 - policy.sell_fee_rate)
    cost = entry_fill * (1 + policy.buy_fee_rate)
    return (proceeds / cost - 1) * 100


def _stop_price(entry_fill: float, policy: TradePolicy) -> float | None:
    if policy.stop_loss_pct is None:
        return None
    cost = Decimal(str(entry_fill)) * (1 + Decimal(str(policy.buy_fee_rate)))
    proceeds_ratio = (1 - Decimal(str(policy.slippage_rate))) * (1 - Decimal(str(policy.sell_fee_rate)))
    price = cost * (1 - Decimal(str(policy.stop_loss_pct))) / proceeds_ratio
    return float(price.quantize(Decimal("0.01"), rounding=ROUND_FLOOR))


def _close_trade(result: TradeReplay, index: int, price: float, reason: str,
                 policy: TradePolicy, timing: str = "open") -> TradeReplay:
    result.status = "closed"
    result.exit_index, result.exit_price = index, price
    result.exit_fill_price = price * (1 - policy.slippage_rate)
    result.exit_timing = timing
    result.exit_reason, result.pending_exit_reason = reason, None
    result.reserved_until_index = index
    result.net_return_pct = _net_return(price, result.entry_fill_price, policy)
    result.mark_return_pct = None
    return result


def _validate(stock: StockSeries, signal_index: int) -> None:
    if not 0 <= signal_index < len(stock.bars):
        raise ValueError("Signal index is outside the supplied history")
    previous_date = None
    for bar in stock.bars:
        values = (bar.open, bar.high, bar.low, bar.close, bar.pct, bar.volume)
        if (bar.date is None or not all(math.isfinite(value) for value in values)
                or min(values[:4]) <= 0 or bar.volume < 0
                or not bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
                or (previous_date is not None and bar.date <= previous_date)):
            raise ValueError("Replay requires finite, ordered, dated OHLCV bars")
        previous_date = bar.date


def replay_trade(stock: StockSeries, signal_index: int,
                 policy: TradePolicy | None = None) -> TradeReplay:
    """Use only information available before each order; never optimize future fills.

    Opening lower-limit sells are conservatively deferred even if they unlock
    later. Price limits and cents are approximations on the supplied QFQ bars.
    """
    policy = policy or TradePolicy()
    _validate(stock, signal_index)
    bars = stock.bars
    raw_limit = Decimal(str(bars[signal_index].close)) * (1 - Decimal(str(policy.dip_pct)))
    limit = float(raw_limit.quantize(Decimal("0.01"), rounding=ROUND_FLOOR))
    if limit <= 0:
        raise ValueError("Entry limit must be positive after tick rounding")
    last = len(bars) - 1
    window_end = min(signal_index + policy.entry_sessions, last)
    result = TradeReplay(status="entry_pending", signal_index=signal_index,
                         limit_price=limit, reserved_until_index=signal_index + policy.entry_sessions)
    for index in range(signal_index + 1, window_end + 1):
        bar = bars[index]
        if bar.volume <= 0:
            continue
        upper_open = bar.open / bars[index - 1].close >= 1.098
        if bar.open <= limit and not upper_open:
            price = bar.open
        elif bar.low < limit and bar.high >= limit:
            price = limit
        else:
            continue
        result.entry_index, result.entry_price = index, price
        result.entry_fill_price = min(price * (1 + policy.slippage_rate), limit)
        result.status = "open"
        result.reserved_until_index = len(bars)
        break
    if result.entry_index is None:
        if last - signal_index >= policy.entry_sessions:
            result.status = "unfilled"
        return result

    result.stop_trigger_price = _stop_price(result.entry_fill_price, policy)

    owned_streak = 0
    ever_owned_board = False
    worst_close = 0.0
    for index in range(result.entry_index, len(bars)):
        bar = bars[index]
        result.holding_sessions = index - result.entry_index + 1
        sellable = bar.volume > 0 and bar.open / bars[index - 1].close > .902
        stop = result.stop_trigger_price
        if (index > result.entry_index and stop is not None
                and bar.open <= stop):
            result.pending_exit_reason = "stop_loss"
            if result.stop_trigger_index is None:
                result.stop_trigger_index = index
        pending = result.pending_exit_reason
        blocked_this_session = False
        if pending and index > result.entry_index:
            opening_return = _net_return(bar.open, result.entry_fill_price, policy)
            if sellable and (pending != "profit" or opening_return > 0):
                return _close_trade(result, index, bar.open, pending, policy)
            if not sellable:
                result.blocked_exit_sessions += 1
                blocked_this_session = True
            if pending == "profit":
                result.profit_orders_cancelled += 1
                result.pending_exit_reason = None

        # The standing stop precedes any closing-board decision, but cannot
        # retroactively replace a sale that already executed at today's open.
        if (index > result.entry_index and stop is not None
                and bar.low <= stop):
            if result.stop_trigger_index is None:
                result.stop_trigger_index = index
            result.pending_exit_reason = "stop_loss"
            if sellable:
                return _close_trade(result, index, stop, "stop_loss", policy, "stop_price")
            if not blocked_this_session:
                result.blocked_exit_sessions += 1

        mark = _net_return(bar.close, result.entry_fill_price, policy)
        worst_close = min(worst_close, mark)
        result.mark_return_pct = mark
        result.worst_close_return_pct = worst_close
        sealed = bar.volume > 0 and _limit_shape(bar)
        owned_streak = owned_streak + 1 if sealed else 0
        result.max_owned_board_streak = max(result.max_owned_board_streak, owned_streak)
        ever_owned_board = ever_owned_board or sealed

        # A mandatory order survives blocked sessions; a later board cannot
        # retroactively cancel either that order or an already executed sale.
        if result.pending_exit_reason in ("timeout", "broken_streak", "stop_loss"):
            continue
        # Entry-day lows may precede an intraday fill and cannot be sold under
        # T+1. Only an entry-day close breach queues a stop for the next open.
        if stop is not None and bar.close <= stop:
            result.pending_exit_reason = "stop_loss"
            result.stop_trigger_index = index
        elif result.holding_sessions >= policy.max_holding_sessions:
            result.pending_exit_reason = "timeout"
        elif sealed:
            result.pending_exit_reason = None
        elif ever_owned_board:
            result.pending_exit_reason = "broken_streak"
        elif mark > 0:
            result.pending_exit_reason = "profit"
    return result
