from datetime import date, timedelta

import pytest

from app.domain.strategies import PriceBar, StockSeries, evaluate_small_cap_absorption


def sample(tail=(), *, probe_changes=None):
    bars = []
    previous = 10
    for i, (close, volume) in enumerate([(10, 100)] * 25 + list(tail)):
        bars.append(PriceBar(date=date(2026, 7, 1) + timedelta(days=i),
                             open=min(previous, close), high=max(previous, close),
                             low=min(previous, close), close=close,
                             pct=(close / previous - 1) * 100, volume=volume))
        previous = close
    if probe_changes:
        bars[25] = bars[25].model_copy(update=probe_changes)
    return StockSeries(symbol="600001", name="精筛样本", market_cap=9e9, bars=bars)


def test_single_volume_probe_is_not_a_production_candidate():
    assert not evaluate_small_cap_absorption(sample([(10.4, 250)])).matched


def test_contracted_supported_pullback_enters_shortlist_with_evidence():
    result = evaluate_small_cap_absorption(sample([(10.4, 250), (10.2, 100), (10.1, 80)]))
    assert result.matched
    assert result.factors["rule_version"] == 4
    assert result.factors["shortlist_qualified"] is True
    assert result.factors["consolidation_volume_ratio"] == .36
    assert result.factors["probe_gain_pct"] == 4
    assert result.factors["stage"] == "pullback"


@pytest.mark.parametrize("tail,changes", [
    ([(10.4, 150), (10.2, 70), (10.1, 60)], None),
    ([(10.1, 250), (10.05, 80), (10, 70)], None),
    ([(10.4, 250), (10.2, 100), (10.1, 80)], {"high": 11}),
    ([(10.4, 250), (10.2, 240), (10.1, 230)], None),
    ([(10.4, 250), (10.2, 100), (9.8, 80)], None),
    ([(10.4, 250), (11.5, 100), (11.2, 80)], None),
    ([(11.5, 250), (10.2, 100), (10.1, 80)], None),
    ([(11, 110), (10.5, 40), (10.4, 35)], None),
])
def test_shortlist_rejects_weak_probes_distribution_broken_support_and_chasing(tail, changes):
    assert not evaluate_small_cap_absorption(sample(tail, probe_changes=changes)).matched


def test_yesterday_only_double_volume_is_not_enough():
    stock = sample([(10.4, 160), (10.2, 60), (10.1, 50)])
    stock.bars[24].volume = 50
    assert not evaluate_small_cap_absorption(stock).matched


def test_age_twelve_is_included_but_thirteen_expires():
    tail = [(10.4, 250)] + [(10.1, 80)] * 12
    assert evaluate_small_cap_absorption(sample(tail)).matched
    assert not evaluate_small_cap_absorption(sample(tail + [(10.1, 80)])).matched


def test_current_recovery_uses_pre_confirmation_contraction_not_today_volume():
    tail = [(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 300)]
    result = evaluate_small_cap_absorption(sample(tail))
    assert result.matched
    assert result.factors["stage"] == "second_volume"
    assert result.factors["consolidation_volume_ratio"] == .36
    assert result.factors["confirmation_age_days"] == 0
    assert not evaluate_small_cap_absorption(sample(tail + [(10.35, 90)] * 3)).matched


@pytest.mark.parametrize("following,label", [([], "首板确认"), ([(12.221, 180)], "二板确认")])
def test_fresh_first_or_second_board_confirmation_is_not_rejected_by_watch_pool_chase_limit(following, label):
    tail = [(10.4, 250), (10.2, 100), (10.1, 80), (11.11, 300)] + following
    result = evaluate_small_cap_absorption(sample(tail))
    assert result.matched
    assert result.factors["entry_signal"] == label
    assert result.factors["gain_since_probe_pct"] > 6


def test_waiting_setup_is_not_labelled_an_entry_signal():
    result = evaluate_small_cap_absorption(sample([(10.4, 250), (10.2, 100), (10.1, 80)]))
    assert result.factors["entry_signal"] == "待放量确认"


def test_non_board_breakout_still_does_not_bypass_the_chase_limit():
    tail = [(10.4, 250), (10.2, 100), (10.1, 80), (11.05, 300)]
    assert not evaluate_small_cap_absorption(sample(tail)).matched


def test_confirmation_rejects_contraction_relative_to_an_unrelated_peak():
    tail = [(10.4, 200), (10.5, 500), (10.3, 200), (10.2, 200), (10.45, 400)]
    assert not evaluate_small_cap_absorption(sample(tail)).matched


def test_weak_earlier_probe_does_not_hide_later_quality_probe():
    tail = [(10.1, 200), (10, 80), (10.5, 300), (10.3, 100), (10.2, 80)]
    result = evaluate_small_cap_absorption(sample(tail))
    assert result.matched
    assert result.factors["probe_date"] == "2026-07-28"


def test_expired_quality_probe_does_not_hide_a_new_setup():
    tail = [(10.4, 250)] + [(10.1, 80)] * 12 + [(10.5, 300), (10.3, 100), (10.2, 80)]
    result = evaluate_small_cap_absorption(sample(tail))
    assert result.matched
    assert result.factors["probe_date"] == "2026-08-08"


def test_contraction_threshold_is_inclusive():
    tail = [(10.4, 200), (10.2, 130), (10.1, 130)]
    assert evaluate_small_cap_absorption(sample(tail)).matched
    assert not evaluate_small_cap_absorption(sample(tail[:-1] + [(10.1, 130.01)])).matched


def test_prefixes_do_not_receive_a_future_confirmation():
    stock = sample([(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 300)])
    earlier = evaluate_small_cap_absorption(stock.model_copy(update={"bars": stock.bars[:-1]}))
    later = evaluate_small_cap_absorption(stock)
    assert "confirmation_date" not in earlier.factors
    assert earlier.factors["stage"] == "pullback"
    assert later.factors["confirmation_date"] == stock.bars[-1].date.isoformat()
