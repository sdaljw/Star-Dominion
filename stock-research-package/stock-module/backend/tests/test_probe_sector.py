from datetime import date, datetime, timedelta
import json
import pytest

from app.domain.market_lines import MarketEnvironment, MarketLineEntry, MarketLineMember, MarketLineSnapshot
from app.domain.strategies import PriceBar, StockSeries
from app.domain.probe_sector import build_probe_sector_context
from app.integrations.candidate_sources import SmallCapAbsorptionSnapshotSource
from app.repositories.market_lines import MarketLineHistoryRepository


def stock():
    return StockSeries(symbol="000504", name="南华生物", market_cap=5e9, bars=[
        PriceBar(date=date(2026, 9, 1) + timedelta(days=i), open=10, high=10.1,
                 low=9.9, close=10, pct=0, volume=100) for i in range(12)
    ])


def history(day, *, symbol="000504", peers=True, ladder=True):
    members = [MarketLineMember(symbol=symbol, name="样本", pct=10, consecutive_boards=1, market_cap_yuan=5e9)]
    if peers:
        members += [MarketLineMember(symbol="600001", name="同行甲", pct=10, consecutive_boards=1, market_cap_yuan=5e9),
                    MarketLineMember(symbol="600002", name="同行乙", pct=10, consecutive_boards=2 if ladder else 1, market_cap_yuan=5e9)]
    return MarketLineSnapshot(status="fresh", as_of_date=date(2026, 9, day),
        generated_at=datetime.fromisoformat(f"2026-09-{day:02d}T16:00:00+08:00"), source="同花顺",
        concept_acquired_at=datetime.fromisoformat(f"2026-09-{day:02d}T15:30:00+08:00"),
        market_environment=MarketEnvironment(label="偏强"), lines=[MarketLineEntry(
            name="医药", code="301000", source_rank=1, score=80, label="主线候选", rank=1,
            pct=2, turnover_yi=100, up_count=70, down_count=30, breadth_score=70,
            persistence_count=1, ladder_score=50, activity_score=80,
            ladder_tiers={"first_board": 2, "second_board": 1, "three_plus_board": 0},
            known_bar_count=len(members), eligible_small_cap_count=len(members),
            eligible_member_symbols=[m.symbol for m in members], members=members,
        )])


def test_probe_during_confirmed_sector_cycle_has_dated_peer_ladder_evidence():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [history(8), history(9), history(10)])
    assert context["probe_sector_status"] == "confirmed"
    assert context["probe_sector_name"] == "医药"
    assert context["probe_sector_date"] == "2026-09-10"
    assert context["probe_sector_cycle_days"] == 3
    assert context["probe_sector_cycle_confirmed"] is True
    assert context["probe_sector_peer_limitups"] == 2
    assert context["probe_sector_ladder_confirmed"] is True
    assert "南华生物" not in context["probe_sector_peers"]


def test_future_or_current_hot_sector_cannot_be_backdated_to_probe():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-08"}, [history(10)])
    assert context["probe_sector_status"] == "unavailable"
    assert "probe_sector_name" not in context


def test_membership_on_signal_date_is_required():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [history(10, symbol="000505")])
    assert context["probe_sector_status"] == "unavailable"


def test_candidate_alone_cannot_prove_peer_sector_effect():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [history(10, peers=False)])
    assert context["probe_sector_status"] == "not_confirmed"


def test_single_day_peer_moves_are_not_called_a_sustained_cycle_or_a_ladder():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [history(10, ladder=False)])
    assert context["probe_sector_status"] == "confirmed"
    assert context["probe_sector_cycle_confirmed"] is False
    assert context["probe_sector_ladder_confirmed"] is False


def test_missing_days_do_not_reach_further_back_to_create_three_day_cycle():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [history(3), history(5), history(10)])
    assert context["probe_sector_cycle_days"] == 1
    assert context["probe_sector_cycle_confirmed"] is False


def test_confirmation_context_is_independent_of_missing_probe_history():
    context = build_probe_sector_context(stock(), {"probe_date": "2026-09-08", "confirmation_date": "2026-09-10"}, [history(10)])
    assert context["probe_sector_status"] == "unavailable"
    assert context["confirmation_sector_status"] == "confirmed"
    assert context["confirmation_sector_date"] == "2026-09-10"


@pytest.mark.parametrize("acquired", [None, "2026-09-10T09:00:00+08:00", "2026-09-09T16:00:00+08:00",
    "2026-09-10T17:00:00+08:00", "2026-09-10T15:30:00"])
def test_hot_theme_rejects_unknown_intraday_wrong_date_future_or_naive_acquisition(acquired):
    snapshot = history(10).model_copy(update={"hot_rank_basis": "concept_gain_rank",
        "concept_acquired_at": datetime.fromisoformat(acquired) if acquired else None})
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [snapshot])
    assert context["confirmation_sector_status"] == "confirmed"
    assert context["confirmation_hot_theme_status"] == "unavailable"


def test_empty_or_stale_history_does_not_claim_sector_support():
    for snapshots in ([], [history(10).model_copy(update={"status": "stale"})]):
        context = build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, snapshots)
        assert context["probe_sector_status"] == "unavailable"


def test_future_generated_snapshot_and_non_mainboard_peers_are_not_evidence():
    future = history(10).model_copy(update={"generated_at": datetime.fromisoformat("2026-09-11T16:00:00+08:00")})
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [future])["probe_sector_status"] == "unavailable"
    wrong = history(10)
    wrong.lines[0].members[1].symbol = "300001"
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [wrong])["probe_sector_status"] == "not_confirmed"


def test_prefixed_input_symbol_still_excludes_the_candidate_from_its_peers():
    prefixed = stock().model_copy(update={"symbol": "sz000504"})
    context = build_probe_sector_context(prefixed, {"probe_date": "2026-09-10"}, [history(10)])
    assert context["probe_sector_peer_limitups"] == 2


def test_adapter_adds_historical_context_and_ignores_broken_history(tmp_path):
    sample = stock()
    for index, close, volume in ((9, 10.4, 250), (10, 10.2, 100), (11, 10.1, 80)):
        previous = sample.bars[index - 1].close
        sample.bars[index] = sample.bars[index].model_copy(update={
            "open": min(previous, close), "high": max(previous, close), "low": min(previous, close),
            "close": close, "volume": volume, "pct": (close / previous - 1) * 100,
        })
    path = tmp_path / "latest.json"
    path.write_text(json.dumps({"small_cap_status": "ok", "small_cap_stocks": [sample.model_dump(mode="json")]}), encoding="utf-8")
    history_path = tmp_path / "market-line-history.json"
    MarketLineHistoryRepository(history_path).save(history(10))
    source = SmallCapAbsorptionSnapshotSource(path)
    assert source.load().items[0].sources[0].factors["probe_sector_name"] == "医药"
    history_path.write_text("broken", encoding="utf-8")
    assert source.load().items[0].sources[0].factors["probe_sector_status"] == "unavailable"


def test_breadth_threshold_and_positive_sector_return_are_both_required():
    snapshot = history(10)
    snapshot.lines[0].breadth_score = 59.99
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [snapshot])["probe_sector_status"] == "not_confirmed"
    snapshot.lines[0].breadth_score = 60
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [snapshot])["probe_sector_status"] == "confirmed"
    snapshot.lines[0].pct = 0
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [snapshot])["probe_sector_status"] == "not_confirmed"


def test_duplicate_peer_or_st_peer_cannot_count_twice():
    snapshot = history(10)
    snapshot.lines[0].members[-1] = snapshot.lines[0].members[1]
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [snapshot])["probe_sector_status"] == "not_confirmed"
    snapshot = history(10)
    snapshot.lines[0].members[-1].name = "ST同行"
    assert build_probe_sector_context(stock(), {"probe_date": "2026-09-10"}, [snapshot])["probe_sector_status"] == "not_confirmed"


@pytest.mark.parametrize("rank,status", [(1, "confirmed"), (10, "confirmed"), (11, "confirmed"), (20, "confirmed"), (21, "not_confirmed")])
def test_hot_theme_accepts_documented_top_twenty_gain_rank(rank, status):
    snapshot = history(10).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    snapshot.lines[0].source_rank = rank
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [snapshot])
    assert context["confirmation_sector_status"] == "confirmed"
    assert context["confirmation_hot_theme_status"] == status
    if status == "confirmed":
        assert context["confirmation_hot_theme_rank"] == rank
        assert context["confirmation_hot_theme_basis"] == "concept_gain_rank"


def test_rank_without_known_ranking_basis_is_not_hot_evidence():
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [history(10)])
    assert context["confirmation_sector_status"] == "confirmed"
    assert context["confirmation_hot_theme_status"] == "unavailable"


def test_hot_snapshot_map_overrides_line_rank_and_future_rank_is_not_borrowed():
    snapshot = history(10).model_copy(update={"hot_rank_basis": "concept_gain_rank",
                                             "hot_concept_ranks": {"医药": 21}})
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [snapshot])
    assert context["confirmation_hot_theme_status"] == "not_confirmed"
    assert build_probe_sector_context(stock(), {"confirmation_date": "2026-09-09"}, [snapshot])[
        "confirmation_hot_theme_status"] == "unavailable"


def test_hot_weak_line_qualifies_independently_without_claiming_sector_effect():
    snapshot = history(10).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    cold = snapshot.lines[0].model_copy(update={"source_rank": 21})
    hot = snapshot.lines[0].model_copy(update={"name": "热门测试题材", "code": "302000", "source_rank": 1,
                                              "members": snapshot.lines[0].members[:1]})
    snapshot.lines = [cold, hot]
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [snapshot])
    assert context["confirmation_sector_status"] == "confirmed"
    assert context["confirmation_hot_theme_status"] == "confirmed"
    assert context["confirmation_hot_theme_sector_confirmed"] is False


def test_top_twenty_theme_without_other_peers_is_hot_but_not_sector_linked():
    snapshot = history(10, peers=False).model_copy(update={"hot_rank_basis": "concept_gain_rank"})
    snapshot.lines[0].source_rank = 20
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, [snapshot])
    assert context["confirmation_sector_status"] == "not_confirmed"
    assert context["confirmation_hot_theme_status"] == "confirmed"
    assert context["confirmation_hot_theme_sector_confirmed"] is False
    assert context["confirmation_hot_theme_cycle_confirmed"] is False


def test_strongest_cold_cycle_does_not_hide_an_alternative_qualifying_hot_theme():
    snapshots = [history(day).model_copy(update={"hot_rank_basis": "concept_gain_rank"}) for day in (8, 9, 10)]
    for snapshot in snapshots:
        snapshot.lines[0].source_rank = 21
    last = snapshots[-1]
    hot = last.lines[0].model_copy(update={"name": "热门测试题材", "code": "302000", "source_rank": 2})
    last.lines.append(hot)
    context = build_probe_sector_context(stock(), {"confirmation_date": "2026-09-10"}, snapshots)
    assert context["confirmation_sector_name"] == "医药"
    assert context["confirmation_hot_theme_name"] == "热门测试题材"
    assert context["confirmation_hot_theme_status"] == "confirmed"
