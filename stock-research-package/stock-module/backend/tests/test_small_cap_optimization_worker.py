from datetime import date, timedelta
import importlib
import json
import math

import pytest

from app.domain.strategies import PriceBar, StockSeries


@pytest.fixture
def worker():
    try:
        return importlib.import_module("workers.optimize_small_cap_policy")
    except ModuleNotFoundError:
        pytest.fail("The read-only optimization worker is not implemented")


def trade(day="2026-06-26", *, symbol="000001", result=2, future=33, status="closed"):
    return {"symbol": symbol, "signal_date": day, "available_future_sessions": future,
            "status": status, "net_return_pct": result if status == "closed" else None,
            "holding_sessions": 3, "exit_reason": "profit" if result > 0 else "stop_loss",
            "mark_return_pct": -4 if status == "open" else None}


def test_candidates_are_frozen_and_preserve_the_users_exit_policy(worker):
    assert len(worker.TRIALS) == 11
    assert len({item.id for item in worker.TRIALS}) == 11
    assert worker.TRIALS[0].id == "baseline"
    assert {item.dip_pct for item in worker.TRIALS} == {.01, .02, .03}
    for item in worker.TRIALS:
        policy = item.policy()
        assert policy.stop_loss_pct == .07
        assert policy.entry_sessions == 3
        assert policy.max_holding_sessions == 30


@pytest.mark.parametrize("value,expected", [(6, True), (6.01, False), (None, False),
                                           (math.nan, False), (math.inf, False), ("6", False)])
def test_filter_fails_closed_on_missing_or_invalid_factors(worker, value, expected):
    assert worker.Trial("shallow", max_drawdown_pct=6).accepts({"max_drawdown_pct": value}) is expected
    assert not worker.Trial("shallow", max_drawdown_pct=6).accepts({})


def test_signal_type_diagnostic_does_not_reject_boards_in_other_trials(worker):
    row = {"entry_signal": "首板确认"}
    assert worker.TRIALS[0].accepts(row)
    assert not worker.Trial("ordinary", ordinary_only=True).accepts(row)
    assert worker.Trial("ordinary", ordinary_only=True).accepts({"entry_signal": "放量转强"})


def test_training_prices_stop_before_validation_and_do_not_modify_source(worker):
    bars = [PriceBar(date=date(2026, 6, 24) + timedelta(days=i), open=10, high=10,
                     low=10, close=10, pct=0, volume=100) for i in range(4)]
    stock = StockSeries(symbol="000001", name="fixture", market_cap=5e9, bars=bars)
    cut = worker.truncate_stocks({stock.symbol: stock}, date(2026, 6, 26))
    assert [bar.date for bar in cut[stock.symbol].bars] == [date(2026, 6, 24), date(2026, 6, 25)]
    assert len(stock.bars) == 4


@pytest.mark.parametrize("invalid_date", [None, date(2026, 6, 23)])
def test_training_truncation_rejects_undated_or_out_of_order_input(worker, invalid_date):
    bars = [PriceBar(date=date(2026, 6, 24), open=10, high=10, low=10, close=10, pct=0, volume=100),
            PriceBar(date=invalid_date, open=10, high=10, low=10, close=10, pct=0, volume=100)]
    stock = StockSeries(symbol="000001", name="fixture", market_cap=5e9, bars=bars)
    with pytest.raises(ValueError, match="ordered.*dated"):
        worker.truncate_stocks({stock.symbol: stock}, date(2026, 6, 26))


def test_signal_contribution_counts_unfilled_and_filtered_as_zero(worker):
    rows = [trade(result=4), trade(symbol="000002", status="unfilled"),
            trade(symbol="000003", result=100, future=32)]
    stats = worker.opportunity_metrics(rows, 10)
    assert stats["signals"] == 2
    assert stats["mean_net_return_pct"] == 4
    assert stats["return_per_original_signal_pct"] == .4
    assert stats["original_signals"] == 10
    assert stats["unfilled_entries"] == 1
    assert worker.opportunity_metrics([], 0)["return_per_original_signal_pct"] is None


def test_later_signals_are_not_added_to_frozen_validation_even_with_enough_future_bars(worker):
    rows = [trade("2026-08-10", result=1, future=40), trade("2026-08-11", result=100, future=40)]
    stats = worker.opportunity_metrics(rows, 1, end_date=date(2026, 8, 10))
    assert stats["closed_trades"] == 1
    assert stats["return_per_original_signal_pct"] == 1
    interval = worker.paired_date_interval(rows, rows, end_date=date(2026, 8, 10))
    assert interval["original_signals"] == 1


def training_stats(mean=1, contribution=.8, count=100, **extra):
    return {"mean_net_return_pct": mean, "return_per_original_signal_pct": contribution,
            "closed_trades": count, "open_trades": 0, "entry_pending": 0, "invalid_data": 0,
            **extra}


def test_selection_uses_signal_contribution_not_just_high_trade_average(worker):
    stats = {"baseline": training_stats(),
             "dip_2": training_stats(mean=4, contribution=.6, count=40),
             "dip_3": training_stats(mean=2, contribution=1.2, count=60)}
    assert worker.select_training_trial(stats) == "dip_3"


@pytest.mark.parametrize("extra", [{"closed_trades": 29}, {"closed_trades": 34},
                                   {"open_trades": 1}, {"entry_pending": 1}, {"invalid_data": 1}])
def test_tiny_or_unfinished_candidates_cannot_be_selected(worker, extra):
    stats = {"baseline": training_stats(),
             "dip_2": training_stats(mean=5, contribution=2, **extra)}
    assert worker.select_training_trial(stats) is None


def test_no_improvement_or_no_training_sample_produces_no_winner(worker):
    assert worker.select_training_trial({"baseline": training_stats(count=0)}) is None
    assert worker.select_training_trial({"baseline": training_stats(),
        "dip_2": training_stats(mean=1.1, contribution=.9)}) is None


def test_less_negative_returns_are_not_selected_as_a_profitable_strategy(worker):
    assert worker.select_training_trial({"baseline": training_stats(mean=-3, contribution=-2),
        "dip_2": training_stats(mean=-.5, contribution=-.3)}) is None


def test_paired_interval_preserves_original_denominator_and_same_date_clusters(worker):
    base = [trade(f"2026-07-{day:02d}", symbol=f"000{day:03d}", result=1) for day in range(1, 7)]
    candidate = [{**row, "net_return_pct": 2} for row in base]
    interval = worker.paired_date_interval(base, candidate, repetitions=100)
    assert interval["date_clusters"] == 6
    assert interval["mean_difference_pct"] == 1
    assert interval["lower_pct"] == interval["upper_pct"] == 1
    assert worker.paired_date_interval(base, candidate, repetitions=100) == interval
    # Excluded signals have zero contribution, not a disappeared denominator.
    sparse = worker.paired_date_interval(base, [], repetitions=100)
    assert sparse["mean_difference_pct"] == -1
    same_day = [{**row, "signal_date": "2026-07-01"} for row in base]
    assert worker.paired_date_interval(same_day, same_day)["lower_pct"] is None


def test_unfinished_mature_trade_has_no_false_precise_interval(worker):
    base = [trade(f"2026-07-{day:02d}", symbol=f"000{day:03d}") for day in range(1, 7)]
    candidate = [*base[:-1], trade("2026-07-06", symbol="000006", status="open")]
    assert worker.paired_date_interval(base, candidate)["lower_pct"] is None


def test_selected_candidate_is_not_replaced_after_bad_validation(worker):
    def bar(day, opening=10, low=10, close=10, high=10.3):
        return PriceBar(date=day, open=opening, low=low, close=close, high=high, volume=100, pct=0)

    start, later = date(2026, 5, 1), date(2026, 6, 26)
    early = [bar(start), bar(start + timedelta(days=1), low=9.7, close=9.9)]
    early += [bar(start + timedelta(days=i)) for i in range(2, 36)]
    late = [bar(later), bar(later + timedelta(days=1), opening=9.9, low=9.85),
            bar(later + timedelta(days=2), opening=10.3, low=9.9, close=10.3),
            bar(later + timedelta(days=3), opening=9.7, low=9.6, close=9.7),
            bar(later + timedelta(days=4), opening=9, low=8.9, close=9, high=9.1)]
    late += [bar(later + timedelta(days=i), opening=9, low=9, close=9, high=9) for i in range(5, 36)]
    stocks = {f"000{i:03d}": StockSeries(symbol=f"000{i:03d}", name="fixture", market_cap=5e9,
                                        bars=early + late) for i in range(1, 31)}

    def signals(index, day, future):
        return [{"symbol": symbol, "signal_index": index, "signal_date": day.isoformat(),
                 "available_future_sessions": future, "entry_signal": "首板确认",
                 "sector_status": "unavailable", "sector_cycle_confirmed": False,
                 "sector_ladder_confirmed": False} for symbol in stocks]

    windows = worker.ResearchWindows(worker.truncate_stocks(stocks, later),
                                     signals(0, start, 35), signals(len(early), later, 35))
    result = worker.run_experiment(stocks, [], train_start=start, validation_start=later,
                                  require_sector=False, windows=windows)
    assert result["selected_trial_id"] == "dip_2"
    assert result["assessment"] == "rejected_validation"
    assert result["selected_trades"]["validation"][0]["exit_reason"] == "stop_loss"
    assert result["baseline"]["validation"]["mean_net_return_pct"] > 0
    assert result["cost_stress"][0]["cost_multiplier"] == 1.5
    assert result["cost_stress"][1]["selected"]["mean_net_return_pct"] < 0
    assert result["production_defaults_changed"] is False


def test_missing_sector_experiment_does_not_optimize_unfiltered_by_accident(worker):
    from tests.test_small_cap_policy_worker import sample
    stock = sample()
    result = worker.run_experiment({stock.symbol: stock}, [],
        train_start=date(2026, 8, 1), validation_start=date(2026, 9, 1),
        validation_end=date(2026, 9, 1), require_sector=True)
    assert result["selected_trial_id"] is None
    assert result["baseline"]["validation"]["mean_net_return_pct"] is None
    assert result["baseline"]["validation"]["original_signals"] == 0
    assert result["validation_sector_status_counts"] == {"unavailable": 1}
    assert result["entry_price_sensitivity"]["dip_2"]["lower_pct"] is None
    assert result["entry_price_sensitivity"]["dip_3"]["original_signals"] == 0


def test_cli_is_read_only_and_diagnostic_is_opt_in(worker, tmp_path, capsys):
    from tests.test_small_cap_policy_worker import sample
    snapshot = tmp_path / "snapshot.json"
    payload = {"small_cap_status": "ok", "small_cap_stocks": [sample().model_dump(mode="json")]}
    snapshot.write_text(json.dumps(payload), encoding="utf-8")
    before = snapshot.read_bytes()
    result = worker.main(["--snapshot", str(snapshot), "--train-start", "2026-08-01",
                          "--validation-start", "2026-09-01", "--validation-end", "2026-09-01",
                          "--output-dir", str(tmp_path / "out")])
    assert "unfiltered_diagnostic" not in result
    assert result["history_status"] == "missing"
    assert result["production_defaults_changed"] is False
    assert result["requested_sector"]["selected_trial_id"] is None
    assert snapshot.read_bytes() == before
    assert json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))["trial_count"] == 11
    assert "snapshot_sha256" in capsys.readouterr().out


def test_fixed_entry_sensitivity_is_available_without_picking_a_validation_winner(worker):
    from tests.test_small_cap_policy_worker import sample
    stock = sample()
    result = worker.run_experiment({stock.symbol: stock}, [], train_start=date(2026, 8, 1),
                                  validation_start=date(2026, 9, 1), validation_end=date(2026, 9, 1),
                                  require_sector=False)
    assert result["selected_trial_id"] is None
    assert set(result["entry_price_sensitivity"]) == {"dip_2", "dip_3"}
    assert result["entry_price_sensitivity"]["dip_2"]["original_signals"] == 1


def test_cli_rejects_date_conflicts_and_input_overwrite(worker, tmp_path):
    from tests.test_small_cap_policy_worker import sample
    snapshot = tmp_path / "summary.json"
    snapshot.write_text(json.dumps({"small_cap_status": "ok", "small_cap_stocks": [
        sample().model_dump(mode="json")]}), encoding="utf-8")
    with pytest.raises(ValueError, match="before"):
        worker.main(["--snapshot", str(snapshot), "--train-start", "2026-09-01",
                     "--validation-start", "2026-09-01", "--validation-end", "2026-09-01",
                     "--output-dir", str(tmp_path / "out")])
    with pytest.raises(ValueError, match="overwrite"):
        worker.main(["--snapshot", str(snapshot), "--train-start", "2026-08-01",
                     "--validation-start", "2026-09-01", "--validation-end", "2026-09-01",
                     "--output-dir", str(tmp_path)])


def test_history_is_parsed_and_hashed_from_a_single_read(worker, tmp_path, monkeypatch):
    from hashlib import sha256
    from pathlib import Path
    from tests.test_small_cap_policy_worker import history
    path = tmp_path / "history.json"
    content = json.dumps([history(1).model_dump(mode="json")]).encode("utf-8")
    path.write_bytes(content)
    read = Path.read_bytes
    reads = []

    def replacing_read(self):
        data = read(self)
        reads.append(self)
        self.write_bytes(b"[]")
        return data

    monkeypatch.setattr(Path, "read_bytes", replacing_read)
    snapshots, status, error, digest = worker.load_history_snapshot(path)
    assert len(snapshots) == 1
    assert status == "loaded"
    assert error is None
    assert digest == sha256(content).hexdigest()
    assert reads == [path]


def test_optimization_dual_filter_has_no_fallback_to_sector_only(worker):
    from tests.test_small_cap_policy_worker import sample, history
    stock = sample()
    kwargs = {"train_start": date(2026, 8, 1), "validation_start": date(2026, 9, 1),
              "validation_end": date(2026, 9, 1), "require_sector": True}
    dual = worker.run_experiment({stock.symbol: stock}, [history(1)], require_hot_theme=True, **kwargs)
    sector = worker.run_experiment({stock.symbol: stock}, [history(1)], **kwargs)
    assert dual["baseline"]["validation"]["original_signals"] == 0
    assert sector["baseline"]["validation"]["original_signals"] == 1
    assert dual["requires_hot_theme"] is True


def test_or_optimization_denominator_includes_hot_only_mature_signals(worker):
    from tests.test_small_cap_policy_worker import sample, history
    stock = sample()
    snapshot = history(1, peers=False).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    snapshot.lines[0].source_rank = 20
    result = worker.run_experiment({stock.symbol: stock}, [snapshot], train_start=date(2026, 8, 1),
        validation_start=date(2026, 9, 1), validation_end=date(2026, 9, 1), require_sector=True,
        require_hot_theme=True, allow_sector_or_hot=True)
    assert result["baseline"]["validation"]["original_signals"] == 1
    assert result["baseline"]["validation"]["closed_trades"] == 1
    assert result["accepts_sector_or_hot"] is True
