"""Legacy wider tracking coverage; production shortlist tests are separate."""

from datetime import date, timedelta
import json
from pathlib import Path

import pytest

from app.domain.strategies import PriceBar, StockSeries
from app.domain.small_cap_probe import track_probe as evaluate_small_cap_absorption


def stock(tail=()):
    values = [(10, 100)] * 25 + list(tail)
    bars = []
    previous = 10
    for i, (close, volume) in enumerate(values):
        bars.append(PriceBar(date=date(2026, 7, 1) + timedelta(days=i),
                             open=min(previous, close), high=max(previous, close),
                             low=min(previous, close), close=close,
                             pct=(close / previous - 1) * 100, volume=volume))
        previous = close
    return StockSeries(symbol="600001", name="样本", market_cap=9e9, bars=bars)


def test_probe_enters_pool_immediately_and_survives_more_than_three_days():
    entry = evaluate_small_cap_absorption(stock([(10.4, 200)]))
    assert entry.matched
    assert entry.factors["stage"] == "probe"
    assert entry.factors["alert_active"] is False
    assert entry.factors["probe_volume_vs_ma5"] == 2
    held = evaluate_small_cap_absorption(stock([(10.4, 200)] + [(10.1, 80)] * 5))
    assert held.matched
    assert held.factors["stage"] == "pullback"
    assert held.factors["probe_date"] == entry.factors["probe_date"]


def test_second_spike_alert_requires_pullback_and_price_recovery():
    result = evaluate_small_cap_absorption(stock([(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 160)]))
    assert result.matched
    assert result.factors["stage"] == "second_volume"
    assert result.factors["alert_active"] is True
    assert result.factors["volume_vs_previous"] == 2
    assert result.factors["volume_vs_ma5"] < 2
    assert result.factors["board_stage"] == "未封板"


@pytest.mark.parametrize("tail", [
    [(10.4, 250), (10.5, 600)],  # 连续放量，未整理
    [(10.4, 250), (10.2, 100), (10.1, 80), (10.0, 200)],  # 放量下跌
    [(10.4, 250), (10.2, 240), (10.1, 230), (10.35, 600)],  # 回落未缩量
])
def test_continuous_spikes_or_distribution_do_not_raise_second_alert(tail):
    result = evaluate_small_cap_absorption(stock(tail))
    assert result.matched
    assert result.factors["alert_active"] is False


def test_confirmation_expires_as_new_alert_but_remains_in_pool():
    tail = [(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 160)]
    before = evaluate_small_cap_absorption(stock(tail[:-1]))
    after = evaluate_small_cap_absorption(stock(tail))
    assert "confirmation_date" not in before.factors
    assert after.factors["alert_active"]
    followup = evaluate_small_cap_absorption(stock(tail + [(10.4, 90)] * 3))
    assert followup.matched
    assert followup.factors["stage"] == "tracking"
    assert followup.factors["alert_active"] is False
    assert followup.factors["confirmation_date"] == after.factors["confirmation_date"]


def test_broken_support_and_expired_probe_leave_pool():
    assert not evaluate_small_cap_absorption(stock([(10.4, 250), (9.6, 100)])).matched
    assert not evaluate_small_cap_absorption(stock([(10.4, 250)] + [(10.1, 80)] * 20)).matched


def test_new_consolidation_after_confirmation_can_trigger_another_wave():
    tail = [(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 160),
            (10.1, 70), (10.0, 60), (10.3, 150)]
    first = evaluate_small_cap_absorption(stock(tail[:4]))
    next_wave = evaluate_small_cap_absorption(stock(tail))
    assert next_wave.factors["confirmation_date"] > first.factors["confirmation_date"]
    assert next_wave.factors["probe_date"] == first.factors["confirmation_date"]


def test_limit_up_can_start_observation_without_double_volume():
    result = evaluate_small_cap_absorption(stock([(11, 110)]))
    assert result.matched
    assert result.factors["probe_kind"] == "涨停形态"
    assert result.factors["board_stage"] == "首板形态"


def test_rejects_three_consecutive_limit_ups_in_recent_30_days():
    sample = stock([(11, 110), (12.1, 120), (13.31, 130)])
    result = evaluate_small_cap_absorption(sample)
    assert not result.matched
    assert "近30天出现连续3板及以上" in result.risk_flags


def test_rejects_five_day_range_at_25_percent_in_recent_30_days():
    sample = stock([(10.1, 100), (10.5, 100), (11.0, 100), (11.5, 100), (12.6, 100)])
    result = evaluate_small_cap_absorption(sample)
    assert not result.matched
    assert "近30天出现5日累计振幅达到25%" in result.risk_flags


def test_does_not_reject_extreme_moves_older_than_30_calendar_days():
    sample = stock([(10, 100)] * 25 + [(11, 100), (12.1, 100), (13.31, 100)] + [(10.4, 100)] * 10)
    for bar in sample.bars[:-10]:
        bar.date -= timedelta(days=40)
    result = evaluate_small_cap_absorption(sample)
    assert "近30天出现连续3板及以上" not in result.risk_flags


def test_exact_drawdown_boundary_is_inclusive():
    assert evaluate_small_cap_absorption(stock([(12, 250), (10.2, 100)])).matched
    assert not evaluate_small_cap_absorption(stock([(12, 250), (10.1988, 100)])).matched


@pytest.mark.parametrize("cap", [None, 0, -1, float("nan"), float("inf"), 1e10])
def test_invalid_or_large_market_cap_is_rejected(cap):
    sample = stock([(10.4, 250)])
    sample.market_cap = cap
    assert not evaluate_small_cap_absorption(sample).matched


@pytest.mark.parametrize("change", [
    {"date": None}, {"volume": float("nan")}, {"volume": -1},
    {"close": float("inf")}, {"low": 0}, {"high": 1},
])
def test_bad_bars_are_rejected(change):
    sample = stock([(10.4, 250)])
    sample.bars[-1] = sample.bars[-1].model_copy(update=change)
    assert not evaluate_small_cap_absorption(sample).matched


def test_duplicate_dates_and_short_history_are_rejected():
    sample = stock([(10.4, 250)])
    sample.bars[-1].date = sample.bars[-2].date
    assert not evaluate_small_cap_absorption(sample).matched
    sample.bars = sample.bars[-5:]
    assert not evaluate_small_cap_absorption(sample).matched


@pytest.mark.parametrize("symbol,name", [("300001", "创业板"), ("600001", "ST样本"), ("600001", "退市样本")])
def test_universe_filters_remain(symbol, name):
    sample = stock([(10.4, 250)])
    sample.symbol, sample.name = symbol, name
    assert not evaluate_small_cap_absorption(sample).matched


def test_real_reference_prefixes_reject_recent_hot_activity_without_backdating():
    raw = json.loads((Path(__file__).parent / "fixtures/small_cap_reference_20260911.json").read_text(encoding="utf-8"))
    results = {}
    for row in raw["stocks"]:
        # Explicit hypothetical eligible cap: this tests shape, NOT historical universe membership.
        sample = StockSeries.model_validate({**row, "market_cap": 9e9})
        daily = {}
        for end in range(6, len(sample.bars) + 1):
            # Only data available on the evaluation day is supplied.
            result = evaluate_small_cap_absorption(sample.model_copy(update={"bars": sample.bars[:end]}))
            if result.matched:
                assert result.factors["trigger_date"] <= sample.bars[end - 1].date.isoformat()
                daily[sample.bars[end - 1].date.isoformat()] = result.factors
        results[row["symbol"]] = daily
    assert "2026-09-11" not in results["000993"]
    assert "2026-09-11" not in results["000930"]
    assert "2026-09-11" not in results["600792"]
    assert results["600792"]["2026-08-19"]["stage"] == "probe"
    assert results["000993"]["2026-09-02"]["stage"] == "probe"
    assert results["000930"]["2026-08-17"]["stage"] == "probe"
    for daily in results.values():
        assert all(factors["trigger_date"] <= day for day, factors in daily.items())
