from datetime import date, timedelta

import pytest

from app.domain import small_cap_backtest as backtest
from app.domain.strategies import PriceBar, StockSeries


def sample(rows):
    previous = 10.0
    bars = []
    for index, (opening, high, low, close) in enumerate([(10, 10, 10, 10), *rows]):
        bars.append(PriceBar(date=date(2026, 7, 1) + timedelta(days=index),
                             open=opening, high=high, low=low, close=close,
                             volume=100, pct=(close / previous - 1) * 100))
        previous = close
    return StockSeries(symbol="600001", name="回测样本", market_cap=5e9, bars=bars)


def replay(rows, **kwargs):
    return backtest.replay_trade(sample(rows), 0, backtest.TradePolicy(**kwargs))


def test_fixed_limit_fills_first_touch_not_the_later_minimum():
    result = replay([(10, 10.1, 9.85, 9.95), (9.5, 9.7, 9.4, 9.6)])
    assert result.entry_index == 1
    assert result.entry_price == 9.9
    assert result.entry_fill_price == 9.9


def test_gap_below_limit_receives_open_price():
    result = replay([(9.8, 9.9, 9.7, 9.8)])
    assert result.entry_price == 9.8
    assert result.entry_fill_price == pytest.approx(9.8 * 1.0005)


def test_third_day_entry_is_allowed_but_fourth_day_is_not():
    rows = [(10, 10.1, 9.95, 10)] * 2 + [(9.8, 9.9, 9.7, 9.8)]
    assert replay(rows).entry_index == 3
    result = replay([(10, 10.1, 9.95, 10)] * 3 + [rows[-1]])
    assert result.status == "unfilled"
    assert result.entry_index is None


def test_touch_without_trading_through_limit_is_not_assumed_filled():
    result = replay([(10, 10.1, 9.9, 10)] * 3)
    assert result.status == "unfilled"


def test_zero_volume_does_not_fill():
    stock = sample([(9.8, 9.9, 9.7, 9.8)] * 3)
    for bar in stock.bars[1:]:
        bar.volume = 0
    assert backtest.replay_trade(stock, 0).status == "unfilled"


def test_entry_day_profit_only_exits_on_the_following_day():
    result = replay([(9.8, 10.1, 9.7, 10), (10.05, 10.1, 10, 10.05)])
    assert result.status == "closed"
    assert result.exit_index == 2
    assert result.exit_reason == "profit"
    assert result.holding_sessions == 2


def test_close_at_gross_profit_but_net_loss_does_not_trigger_sale():
    result = replay([(9.9, 9.95, 9.8, 9.91), (9.92, 9.95, 9.8, 9.91)])
    assert result.status == "open"
    assert result.pending_exit_reason is None


def test_losing_gap_cancels_profit_order_then_waits_for_another_profitable_open():
    result = replay([(9.8, 10.1, 9.7, 10), (9.7, 9.85, 9.6, 9.75),
                     (9.85, 10.1, 9.8, 10), (10.05, 10.1, 10, 10.05)])
    assert result.exit_index == 4
    assert result.net_return_pct > 0
    assert result.profit_orders_cancelled == 1


def test_holding_a_sealed_board_overrides_profitable_close():
    result = replay([(9.8, 11, 9.7, 11), (12.1, 12.1, 12.1, 12.1),
                     (12, 12.2, 11.8, 12), (11.8, 12, 11.7, 11.9)])
    assert result.exit_reason == "broken_streak"
    assert result.exit_index == 4
    assert result.max_owned_board_streak == 2


def test_a_signal_day_board_does_not_count_as_a_board_owned_after_entry():
    stock = sample([(10, 11, 10, 11), (10.8, 10.9, 10.7, 10.8),
                    (10.9, 11, 10.8, 10.9), (11, 11.1, 10.9, 11)])
    result = backtest.replay_trade(stock, 1)
    assert result.exit_reason == "profit"
    assert result.max_owned_board_streak == 0
    assert result.exit_index == 4


def test_intraday_limit_touch_without_sealing_is_not_a_board():
    result = replay([(9.8, 11, 9.7, 10), (10.05, 10.1, 10, 10.05)])
    assert result.exit_reason == "profit"
    assert result.max_owned_board_streak == 0


def test_future_board_cannot_cancel_a_profitable_open_exit():
    result = replay([(9.8, 10.1, 9.7, 10), (10.05, 11, 10, 11)])
    assert result.exit_index == 2
    assert result.exit_reason == "profit"
    assert result.max_owned_board_streak == 0


def test_timeout_is_executed_on_the_thirty_first_holding_session():
    result = replay([(9.8, 9.9, 9.7, 9.8)] * 31)
    assert result.status == "closed"
    assert result.exit_reason == "timeout"
    assert result.exit_index == 31
    assert result.holding_sessions == 31
    assert result.net_return_pct < 0


def test_timeout_also_caps_a_continuing_board_streak():
    result = replay([(9.8, 11, 9.7, 11), (12.1, 12.1, 12.1, 12.1),
                     (13.31, 13.31, 13.31, 13.31), (14.64, 14.64, 14.64, 14.64)],
                    max_holding_sessions=3)
    assert result.exit_reason == "timeout"
    assert result.exit_index == 4


def test_lower_limit_open_defers_a_mandatory_sell_instead_of_faking_fill():
    result = replay([(9.8, 11, 9.7, 11), (10.8, 11, 10.7, 10.8),
                     (9.72, 9.72, 9.72, 9.72), (9.8, 9.9, 9.7, 9.8)])
    assert result.exit_reason == "broken_streak"
    assert result.exit_index == 4
    assert result.blocked_exit_sessions == 1


def test_upper_limit_open_is_not_a_known_buy_fill_even_at_zero_dip():
    stock = sample([(11, 11, 11, 11)])
    result = backtest.replay_trade(stock, 0, backtest.TradePolicy(dip_pct=0))
    assert result.status == "entry_pending"
    assert result.entry_index is None


def test_tail_position_is_open_with_mark_return_not_a_fake_realized_exit():
    result = replay([(9.8, 9.9, 9.7, 9.8)] * 30)
    assert result.status == "open"
    assert result.pending_exit_reason == "timeout"
    assert result.net_return_pct is None
    assert result.mark_return_pct < 0
    assert result.exit_index is None


def test_unfinished_buy_window_is_not_classified_as_unfilled():
    assert replay([(10, 10.1, 9.95, 10)]).status == "entry_pending"


@pytest.mark.parametrize("rows", [[(9.8, 9.9, 9.7, 9.8)] * 2,
                                   [(10, 10.1, 9.95, 10)] * 2])
def test_unresolved_position_or_order_reserves_the_final_observed_bar(rows):
    stock = sample(rows)
    result = backtest.replay_trade(stock, 0)
    assert result.status in ("open", "entry_pending")
    assert result.reserved_until_index > len(stock.bars) - 1


def test_net_return_includes_both_sides_fees_and_slippage():
    result = replay([(9.8, 10.1, 9.7, 10), (10.05, 10.1, 10, 10.05)])
    expected = (10.05 * .9995 * .999 / (9.8 * 1.0005 * 1.001) - 1) * 100
    assert result.net_return_pct == pytest.approx(expected)
    assert result.exit_fill_price == pytest.approx(10.05 * .9995)
    assert result.mark_return_pct is None


def test_adverse_buy_slippage_cannot_exceed_the_limit_price():
    result = replay([(10, 10.1, 9.85, 10), (10.05, 10.1, 10, 10.05)])
    expected = (10.05 * .9995 * .999 / (9.9 * 1.001) - 1) * 100
    assert result.entry_fill_price <= result.limit_price
    assert result.net_return_pct == pytest.approx(expected)


@pytest.mark.parametrize("kwargs", [{"dip_pct": -1}, {"dip_pct": float("nan")},
                                   {"buy_fee_rate": -1}, {"sell_fee_rate": 1},
                                   {"slippage_rate": float("inf")}, {"entry_sessions": 0},
                                   {"max_holding_sessions": 0}])
def test_invalid_policy_is_rejected(kwargs):
    with pytest.raises(ValueError):
        backtest.TradePolicy(**kwargs)


def test_invalid_future_bar_is_rejected_instead_of_creating_a_trade():
    stock = sample([(9.8, 9.9, 9.7, 9.8)])
    stock.bars[-1].low = -1
    with pytest.raises(ValueError):
        backtest.replay_trade(stock, 0)


def stop_replay(rows, **kwargs):
    return replay(rows, dip_pct=0, buy_fee_rate=0, sell_fee_rate=0, slippage_rate=0, **kwargs)


def test_standing_stop_triggers_intraday_even_if_that_day_later_seals_a_board():
    result = stop_replay([(10, 10.1, 9.9, 10), (10, 11, 9.2, 11)])
    assert result.exit_reason == "stop_loss"
    assert result.exit_index == 2
    assert result.stop_trigger_index == 2
    assert result.stop_trigger_price == 9.3
    assert result.exit_price == 9.3
    assert result.exit_timing == "stop_price"
    assert result.net_return_pct == pytest.approx(-7)
    assert result.max_owned_board_streak == 0


def test_gap_below_stop_uses_actual_open_not_an_unavailable_seven_percent_fill():
    result = stop_replay([(10, 10.1, 9.9, 10), (9.1, 9.2, 9, 9.1)])
    assert result.exit_reason == "stop_loss"
    assert result.exit_price == 9.1
    assert result.exit_timing == "open"
    assert result.net_return_pct == pytest.approx(-9)


def test_entry_day_close_stop_waits_for_t_plus_one_and_does_not_cancel_on_recovery():
    result = stop_replay([(10, 10.1, 9, 9.2), (9.4, 9.5, 9.3, 9.4)])
    assert result.entry_index == 1
    assert result.stop_trigger_index == 1
    assert result.exit_index == 2
    assert result.exit_price == 9.4
    assert result.exit_reason == "stop_loss"


def test_entry_day_intraday_low_cannot_create_a_t_plus_zero_stop():
    result = stop_replay([(10, 10.1, 9, 10), (10, 10.1, 9.9, 10)])
    assert result.status == "open"
    assert result.stop_trigger_index is None


def test_lower_limit_stop_remains_pending_and_can_lose_more_than_seven_percent():
    result = stop_replay([(10, 10.1, 9.9, 10), (9, 9, 9, 9), (8.8, 9, 8.6, 8.8)])
    assert result.exit_reason == "stop_loss"
    assert result.stop_trigger_index == 2
    assert result.exit_index == 3
    assert result.exit_price == 8.8
    assert result.blocked_exit_sessions == 1
    assert result.net_return_pct == pytest.approx(-12)


def test_locked_stop_at_end_of_data_is_unresolved_not_a_fake_closed_trade():
    result = stop_replay([(10, 10.1, 9.9, 10), (9, 9, 9, 9)])
    assert result.status == "open"
    assert result.pending_exit_reason == "stop_loss"
    assert result.exit_index is None
    assert result.net_return_pct is None


def test_exact_stop_touch_is_a_market_trigger_not_a_limit_buy_queue():
    result = stop_replay([(10, 10.1, 9.9, 10), (10, 10.1, 9.3, 9.9)])
    assert result.exit_price == 9.3
    assert result.exit_reason == "stop_loss"


def test_just_above_stop_does_not_exit():
    result = stop_replay([(10, 10.1, 9.9, 10), (10, 10.1, 9.31, 9.4)])
    assert result.status == "open"
    assert result.pending_exit_reason is None


def test_stop_overrides_a_queued_profit_exit_when_open_gaps_down():
    result = stop_replay([(10, 10.1, 9.9, 10.1), (9.2, 9.3, 9.15, 9.2)])
    assert result.exit_reason == "stop_loss"
    assert result.exit_price == 9.2


def test_stop_overrides_a_queued_timeout_on_a_gap():
    result = stop_replay([(10, 10.1, 9.9, 10), (9.1, 9.2, 9, 9.1)], max_holding_sessions=1)
    assert result.exit_reason == "stop_loss"


def test_a_later_intraday_low_cannot_relabel_an_already_executed_open_sale():
    result = stop_replay([(10, 10.1, 9.9, 10.1), (10.1, 10.2, 9, 10)])
    assert result.exit_reason == "profit"
    assert result.exit_price == 10.1
    assert result.stop_trigger_index is None


def test_stop_uses_net_costs_and_tick_rounding_without_clamping_return():
    result = replay([(9.8, 9.9, 9.7, 9.8), (9.8, 10, 9, 9.8)])
    assert result.exit_reason == "stop_loss"
    assert result.stop_trigger_price == 9.14
    assert result.net_return_pct <= -7
    assert result.net_return_pct > -7.2


def test_no_volume_cannot_execute_a_stop():
    stock = sample([(10, 10.1, 9.9, 10), (9.1, 9.2, 9, 9.1)])
    stock.bars[-1].volume = 0
    result = backtest.replay_trade(stock, 0, backtest.TradePolicy(dip_pct=0))
    assert result.status == "open"
    assert result.exit_index is None
    assert result.pending_exit_reason == "stop_loss"
    assert result.stop_trigger_index == 2


def test_zero_volume_stop_is_retained_until_the_next_sellable_rebound_open():
    stock = sample([(10, 10.1, 9.9, 10), (9.1, 9.1, 9.1, 9.1), (9.5, 9.6, 9.4, 9.5)])
    stock.bars[2].volume = 0
    policy = backtest.TradePolicy(dip_pct=0, buy_fee_rate=0, sell_fee_rate=0, slippage_rate=0)
    result = backtest.replay_trade(stock, 0, policy)
    assert result.stop_trigger_index == 2
    assert result.exit_reason == "stop_loss"
    assert result.exit_index == 3
    assert result.exit_price == 9.5
    assert result.net_return_pct == pytest.approx(-5)
    assert result.blocked_exit_sessions == 1


def test_stop_can_be_explicitly_disabled_to_preserve_the_original_baseline():
    result = stop_replay([(10, 10.1, 9.9, 10), (10, 10.1, 9.2, 9.4)], stop_loss_pct=None)
    assert result.status == "open"
    assert result.stop_trigger_price is None


@pytest.mark.parametrize("value", [0, -1, 1, float("nan"), float("inf")])
def test_invalid_stop_fraction_is_rejected(value):
    with pytest.raises(ValueError):
        backtest.TradePolicy(stop_loss_pct=value)
