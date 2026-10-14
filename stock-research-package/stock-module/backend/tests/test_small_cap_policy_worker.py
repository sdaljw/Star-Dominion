from datetime import date, datetime, timedelta
import json

import pytest

from app.domain.small_cap_backtest import TradePolicy
from app.domain.market_lines import MarketEnvironment, MarketLineEntry, MarketLineMember, MarketLineSnapshot
from app.domain.strategies import PriceBar, StockSeries
from workers import backtest_small_cap_policy as worker


def history(day, *, peers=True):
    members = []
    if peers:
        members += [MarketLineMember(symbol="600001", name="测试同行甲", pct=10,
                                     consecutive_boards=1, market_cap_yuan=5e9),
                    MarketLineMember(symbol="600002", name="测试同行乙", pct=10,
                                     consecutive_boards=2, market_cap_yuan=5e9)]
    return MarketLineSnapshot(status="fresh", as_of_date=date(2026, 9, day),
        generated_at=datetime.fromisoformat(f"2026-09-{day:02d}T16:00:00+08:00"), source="test fixture",
        concept_acquired_at=datetime.fromisoformat(f"2026-09-{day:02d}T15:30:00+08:00"),
        market_environment=MarketEnvironment(label="偏强"), lines=[MarketLineEntry(
            name="医药", code="301000", source_rank=1, score=80, label="主线候选", rank=1,
            pct=2, turnover_yi=100, up_count=70, down_count=30, breadth_score=70,
            persistence_count=1, ladder_score=50, activity_score=80,
            ladder_tiers={"first_board": 1, "second_board": 1, "three_plus_board": 0},
            known_bar_count=len(members) + 1, eligible_small_cap_count=len(members) + 1,
            eligible_member_symbols=["000504", *[m.symbol for m in members]], members=members)])


def sample(future=33):
    rows = [(10, 100)] * 25 + [(10.4, 250), (10.2, 100), (10.1, 80), (10.35, 300)]
    rows += [(10.1, 80)] * future
    previous = 10
    bars = []
    for index, (close, volume) in enumerate(rows):
        bars.append(PriceBar(date=date(2026, 9, 1) + timedelta(days=index - 28),
                             open=min(previous, close), high=max(previous, close),
                             low=min(previous, close), close=close,
                             pct=(close / previous - 1) * 100, volume=volume))
        previous = close
    return StockSeries(symbol="000504", name="回测测试样本", market_cap=5e9, bars=bars)


def signals(stock, snapshots=()):
    return worker.collect_signals([stock], list(snapshots), date(2026, 8, 1))


def test_only_the_first_actual_confirmation_day_becomes_a_signal():
    stock = sample()
    found = signals(stock)
    assert len(found) == 1
    assert found[0]["signal_index"] == 28
    assert found[0]["signal_date"] == "2026-09-01"
    assert found[0]["confirmation_date"] == found[0]["signal_date"]
    assert found[0]["available_future_sessions"] == 33


def test_valid_confirmation_with_less_than_twenty_five_bars_is_not_lost():
    stock = sample()
    stock = stock.model_copy(update={"bars": stock.bars[20:]})
    found = signals(stock)
    assert len(found) == 1
    assert found[0]["signal_index"] == 8
    assert found[0]["signal_date"] == "2026-09-01"


def test_sector_history_is_required_on_the_confirmation_day_not_today():
    stock = sample()
    assert signals(stock, [history(2)])[0]["sector_status"] == "unavailable"
    found = signals(stock, [history(1)])
    assert found[0]["sector_status"] == "confirmed"
    assert found[0]["sector_name"] == "医药"
    assert found[0]["sector_ladder_confirmed"] is True


def test_missing_sector_has_no_fake_zero_percent_return_or_fallback():
    stock = sample()
    report = worker.run_cohort(signals(stock), {stock.symbol: stock}, TradePolicy(), require_sector=True)
    assert report["eligible_signals"] == 0
    assert report["sector_status_counts"] == {"unavailable": 1}
    assert report["all_observed"]["mean_net_return_pct"] is None
    assert report["mature"]["win_rate_pct"] is None
    assert report["trades"] == []


def test_confirmed_sector_uses_the_requested_trade_policy():
    stock = sample()
    report = worker.run_cohort(signals(stock, [history(1)]), {stock.symbol: stock},
                               TradePolicy(), require_sector=True)
    assert report["eligible_signals"] == 1
    assert report["mature"]["closed_trades"] == 1
    trade = report["trades"][0]
    assert trade["exit_reason"] == "timeout"
    assert trade["holding_sessions"] == 31
    assert trade["entry_date"] == "2026-09-02"
    assert trade["exit_date"] == "2026-10-02"


def test_not_confirmed_sector_is_distinct_from_missing_history():
    stock = sample()
    report = worker.run_cohort(signals(stock, [history(1, peers=False)]), {stock.symbol: stock},
                               TradePolicy(), require_sector=True)
    assert report["sector_status_counts"] == {"not_confirmed": 1}
    assert report["eligible_signals"] == 0


def test_unfiltered_diagnostic_is_explicit_and_tail_trade_is_not_a_win():
    stock = sample(5)
    report = worker.run_cohort(signals(stock), {stock.symbol: stock}, TradePolicy(), require_sector=False)
    assert report["all_observed"]["open_trades"] == 1
    assert report["all_observed"]["closed_trades"] == 0
    assert report["all_observed"]["win_rate_pct"] is None
    assert report["mature"]["signals"] == 0
    assert report["trades"][0]["mark_return_pct"] < 0


def test_active_position_blocks_another_signal_in_the_same_symbol():
    stock = sample()
    found = signals(stock)
    second = {**found[0], "signal_index": 30, "signal_date": stock.bars[30].date.isoformat(),
              "available_future_sessions": 31, "probe_date": stock.bars[29].date.isoformat()}
    report = worker.run_cohort([second, found[0]], {stock.symbol: stock}, TradePolicy(), require_sector=False)
    assert report["all_observed"]["closed_trades"] == 1
    assert report["all_observed"]["overlap_skipped"] == 1


def test_last_day_confirmation_cannot_add_a_buy_order_to_an_open_position():
    stock = sample(2)
    stock.bars.append(PriceBar(date=stock.bars[-1].date + timedelta(days=1),
                               open=10.1, high=10.3, low=10.1, close=10.3,
                               volume=300, pct=(10.3 / 10.1 - 1) * 100))
    found = signals(stock)
    assert len(found) == 2
    assert found[1]["signal_index"] == len(stock.bars) - 1
    report = worker.run_cohort(found, {stock.symbol: stock}, TradePolicy(), require_sector=False)
    assert [row["status"] for row in report["trades"]] == ["open", "overlap_skipped"]


def test_exit_at_open_allows_a_fresh_signal_at_the_same_days_close():
    stock = sample()
    found = signals(stock)
    exit_index = 59
    second = {**found[0], "signal_index": exit_index, "signal_date": stock.bars[exit_index].date.isoformat(),
              "available_future_sessions": len(stock.bars) - exit_index - 1}
    report = worker.run_cohort([*found, second], {stock.symbol: stock}, TradePolicy(), require_sector=False)
    assert report["trades"][0]["exit_index"] == exit_index
    assert report["trades"][1]["status"] == "entry_pending"


def test_summary_reports_losses_and_does_not_compound_overlapping_symbols():
    rows = [{"status": "closed", "net_return_pct": 2, "holding_sessions": 3, "exit_reason": "profit"},
            {"status": "closed", "net_return_pct": -4, "holding_sessions": 31, "exit_reason": "timeout"},
            {"status": "open", "mark_return_pct": -5}]
    summary = worker.summarize_trades(rows)
    assert summary["mean_net_return_pct"] == -1
    assert summary["win_rate_pct"] == 50
    assert summary["profit_factor"] == .5
    assert summary["open_trades"] == 1
    assert summary["worst_net_return_pct"] == -4
    assert summary["mean_losing_return_pct"] == -4
    assert summary["mean_open_mark_return_pct"] == -5
    assert "annualized_return" not in summary


def test_cli_writes_reproducible_audits_without_modifying_inputs(tmp_path):
    stock = sample()
    path = tmp_path / "latest.json"
    original = json.dumps({"small_cap_status": "ok", "small_cap_stocks": [stock.model_dump(mode="json")],
                           "small_cap_generated_at": "2026-10-05T16:00:00+08:00"})
    path.write_text(original, encoding="utf-8")
    out = tmp_path / "report"
    worker.main(["--snapshot", str(path), "--start", "2026-08-01", "--output-dir", str(out),
                 "--include-unfiltered-diagnostic"])
    report = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert report["history_status"] == "missing"
    assert report["requested_sector"]["eligible_signals"] == 0
    assert report["unfiltered_diagnostic"]["mature"]["closed_trades"] == 1
    assert report["execution_policy"]["stop_loss_pct"] == .07
    assert report["policy_version"] == 4
    assert len(report["snapshot_sha256"]) == 64
    assert (out / "signals.csv").exists()
    assert (out / "unfiltered-diagnostic-trades.csv").exists()
    assert path.read_text(encoding="utf-8") == original


def test_broken_history_is_reported_not_silently_treated_as_valid(tmp_path):
    path = tmp_path / "history.json"
    path.write_text("broken", encoding="utf-8")
    snapshots, status, error = worker.load_history(path)
    assert snapshots == []
    assert status == "invalid"
    assert error


def test_bad_snapshot_status_is_rejected(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "failed", "small_cap_stocks": []}), encoding="utf-8")
    with pytest.raises(ValueError):
        worker.main(["--snapshot", str(path), "--output-dir", str(tmp_path / "out")])


def test_unreadable_history_path_is_a_coverage_error_not_a_crash(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "ok",
                               "small_cap_stocks": [sample().model_dump(mode="json")]}), encoding="utf-8")
    history_path = tmp_path / "history-directory"
    history_path.mkdir()
    report = worker.main(["--snapshot", str(path), "--history", str(history_path),
                           "--output-dir", str(tmp_path / "report")])
    assert report["history_status"] == "invalid"
    assert report["history_sha256"] is None
    assert report["requested_sector"]["eligible_signals"] == 0
    assert "unfiltered_diagnostic" not in report


def test_cli_can_disable_stop_for_a_separate_baseline(tmp_path):
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "ok",
                               "small_cap_stocks": [sample().model_dump(mode="json")]}), encoding="utf-8")
    report = worker.main(["--snapshot", str(path), "--no-stop-loss",
                           "--output-dir", str(tmp_path / "baseline")])
    assert report["execution_policy"]["stop_loss_pct"] is None


def test_strict_intersection_diagnostic_does_not_override_production_or_gate(tmp_path):
    from app.integrations.candidate_sources import SmallCapAbsorptionSnapshotSource
    from app.domain.small_cap_entry import build_small_cap_entry_gate
    stock = sample()
    snapshot = history(1).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    found = signals(stock, [snapshot])
    path = tmp_path / "latest.json"
    current = stock.model_copy(update={"bars": stock.bars[:29]})
    path.write_text(json.dumps({"small_cap_status": "ok", "small_cap_stocks": [current.model_dump(mode="json")],
        "small_cap_generated_at": "2026-09-01T16:00:00+08:00"}), encoding="utf-8")
    history_path = path.with_name("market-line-history.json")
    history_path.write_text(json.dumps([snapshot.model_dump(mode="json")]), encoding="utf-8")
    assert SmallCapAbsorptionSnapshotSource(path).load().items[0].sources[0].factors["entry_eligible"] is True
    assert build_small_cap_entry_gate(found[0])["entry_eligible"] is True
    result = worker.run_cohort(found, {stock.symbol: stock}, TradePolicy(), require_sector=True, require_hot_theme=True)
    assert result["eligible_signals"] == 1
    assert result["requires_hot_theme"] is True
    snapshot.lines[0].source_rank = 21
    history_path.write_text(json.dumps([snapshot.model_dump(mode="json")]), encoding="utf-8")
    assert SmallCapAbsorptionSnapshotSource(path).load().items[0].sources[0].factors["entry_basis"] == "sector_only"
    cold = signals(stock, [snapshot])
    assert worker.run_cohort(cold, {stock.symbol: stock}, TradePolicy(), require_sector=True)["eligible_signals"] == 1
    assert worker.run_cohort(cold, {stock.symbol: stock}, TradePolicy(), require_sector=True,
                             require_hot_theme=True)["eligible_signals"] == 0


def test_cli_main_cohort_allows_sector_without_hot_history(tmp_path):
    stock = sample()
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "ok", "small_cap_stocks": [stock.model_dump(mode="json")]}), encoding="utf-8")
    # Valid sector history but old snapshots have no known hot ranking basis.
    history_path = path.with_name("market-line-history.json")
    history_path.write_text(json.dumps([history(1).model_dump(mode="json")]), encoding="utf-8")
    report = worker.main(["--snapshot", str(path), "--start", "2026-08-01", "--output-dir", str(tmp_path / "out")])
    assert report["requested_sector"]["eligible_signals"] == 1
    assert report["requested_sector"]["accepts_sector_or_hot"] is True
    assert report["sector_only_diagnostic"]["eligible_signals"] == 1
    assert report["execution_policy"]["stop_loss_pct"] == .07


def test_hot_theme_requirement_cannot_be_enabled_without_sector_requirement():
    with pytest.raises(ValueError, match="sector"):
        worker.run_cohort([], {}, TradePolicy(), require_sector=False, require_hot_theme=True)


def test_or_replay_accepts_hot_only_rank_twenty_and_matches_production(tmp_path):
    from app.integrations.candidate_sources import SmallCapAbsorptionSnapshotSource
    stock = sample()
    snapshot = history(1, peers=False).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    snapshot.lines[0].source_rank = 20
    found = signals(stock, [snapshot])
    result = worker.run_cohort(found, {stock.symbol: stock}, TradePolicy(), require_sector=True,
        require_hot_theme=True, allow_sector_or_hot=True)
    assert result["eligible_signals"] == 1
    assert result["entry_basis_counts"] == {"hot_theme_only": 1}
    assert worker.run_cohort(found, {stock.symbol: stock}, TradePolicy(), require_sector=True)["eligible_signals"] == 0
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "ok", "small_cap_stocks": [
        stock.model_copy(update={"bars": stock.bars[:29]}).model_dump(mode="json")],
        "small_cap_generated_at": "2026-09-01T16:00:00+08:00"}), encoding="utf-8")
    path.with_name("market-line-history.json").write_text(json.dumps([snapshot.model_dump(mode="json")]), encoding="utf-8")
    assert SmallCapAbsorptionSnapshotSource(path).load().items[0].sources[0].factors["entry_basis"] == "hot_theme_only"
    snapshot.lines[0].source_rank = 21
    assert worker.run_cohort(signals(stock, [snapshot]), {stock.symbol: stock}, TradePolicy(),
        require_sector=True, require_hot_theme=True, allow_sector_or_hot=True)["eligible_signals"] == 0
