from dataclasses import replace
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from app.domain.market_lines import ConceptMarketInput, ConceptMarketMember, MarketEnvironment, score_market_lines
from app.domain.probe_sector import build_probe_sector_context
from app.domain.strategies import StockSeries
from app.repositories.candidate_snapshots import CandidateSnapshotRepository
from app.services.candidate_refresh import CandidateRefreshService
from workers import ths_hot_concepts as ths
from workers.user_strategy_snapshot import refresh_market_line_history
from tests.test_candidate_refresh import FakeSource, _batch
from tests.test_market_lines import _stock_row
from tests.test_ths_hot_concepts import DETAIL_HTML, FUND_FLOW_HTML, FakeResponse


SHANGHAI = ZoneInfo("Asia/Shanghai")
MORNING = datetime(2026, 9, 24, 9, 0, tzinfo=SHANGHAI)
CLOSE = datetime(2026, 9, 24, 16, 0, tzinfo=SHANGHAI)


def test_post_close_collection_refetches_morning_cache(tmp_path: Path):
    calls = []

    class FakeAkshare:
        def stock_board_concept_name_ths(self):
            return pd.DataFrame([{"name": "机器人", "code": "301024"}])

    def getter(url, **kwargs):
        calls.append(url)
        return FakeResponse(FUND_FLOW_HTML if "funds/gnzjl" in url else DETAIL_HTML)

    for now in (MORNING, CLOSE):
        ths.collect_ths_hot_stock_pool(FakeAkshare(), top_concepts=1, max_stocks=10,
            cache_path=tmp_path / "cache.json", http_get=getter, now=now)
    assert len(calls) == 4
    output = []
    ths.collect_ths_hot_stock_pool(FakeAkshare(), top_concepts=1, max_stocks=10,
        cache_path=tmp_path / "cache.json", http_get=getter, now=CLOSE, concepts_output=output)
    assert len(calls) == 4
    assert output[0].acquired_at == CLOSE


def test_morning_or_unknown_concept_acquisition_cannot_create_close_history(tmp_path: Path):
    concept = ths.parse_concept_detail("机器人", "301024", DETAIL_HTML)
    rows = [_stock_row("600001", "样本", 1)]
    breadth = {"advancing": 70, "declining": 30, "quote_count": 100}
    assert refresh_market_line_history(tmp_path / "latest.json", [concept], rows, breadth, CLOSE) is None
    morning = replace(concept, hot_rank=1, acquired_at=MORNING)
    assert refresh_market_line_history(tmp_path / "latest.json", [morning], rows, breadth, CLOSE) is None
    assert not (tmp_path / "market-line-history.json").exists()


def test_unknown_original_rank_is_not_replaced_by_compacted_position(tmp_path: Path):
    concept = replace(ths.parse_concept_detail("旧缓存未知名次", "301024", DETAIL_HTML), acquired_at=CLOSE)
    rows = [_stock_row("600001", "样本", 1)]
    saved = refresh_market_line_history(tmp_path / "latest.json", [concept], rows,
        {"advancing": 70, "declining": 30, "quote_count": 100}, CLOSE)
    assert saved is not None
    assert saved.lines[0].source_rank == 0
    assert concept.name not in saved.hot_concept_ranks
    assert saved.lines[0].persistence_count == 0


def test_display_top_five_does_not_discard_hot_qualification_evidence():
    rows = [_stock_row("600001", "同行甲", 2), _stock_row("000002", "同行乙", 1),
            _stock_row("600003", "额外同行", 3), _stock_row("000504", "样本", 0)]
    members = [ConceptMarketMember(symbol=row["symbol"], name=row["name"], pct=10) for row in rows]
    cold = [ConceptMarketInput(name=f"冷题材{i}", code=f"cold{i}", hot_rank=21 + i, pct=10 + i,
        turnover_yi=1000, up_count=100, down_count=0, members=members) for i in range(5)]
    hot = ConceptMarketInput(name="合格热门题材", code="hot", hot_rank=6, pct=1,
        turnover_yi=10, up_count=60, down_count=40, members=members[:2] + members[3:])
    snapshot = score_market_lines([*cold, hot], [], rows, MarketEnvironment(label="偏强"), CLOSE.date(), CLOSE,
        concept_acquired_at=CLOSE)
    assert len(snapshot.lines) == 5
    assert hot.name not in [line.name for line in snapshot.lines]
    stock = StockSeries.model_validate(rows[3])
    context = build_probe_sector_context(stock, {"confirmation_date": CLOSE.date().isoformat()}, [snapshot])
    assert context["confirmation_hot_theme_status"] == "confirmed"
    assert context["confirmation_hot_theme_name"] == hot.name


def test_stale_status_survives_restart_and_successful_refresh_clears_it(tmp_path: Path):
    source = FakeSource("small_cap_absorption", "小市值", _batch("small_cap_absorption", "小市值", "000001", "样本"))
    database = tmp_path / "hub.db"
    service = CandidateRefreshService(CandidateSnapshotRepository(database), [source])
    service.refresh()
    source.error = "上游失败"
    assert service.refresh().sources[0].status == "stale"
    restarted = CandidateRefreshService(CandidateSnapshotRepository(database), [source])
    assert restarted.get_candidates().sources[0].status == "stale"
    assert restarted.get_candidates().sources[0].error == source.error
    source.error = None
    assert restarted.refresh().sources[0].status == "ok"
    assert CandidateRefreshService(CandidateSnapshotRepository(database), [source]).get_candidates().sources[0].status == "ok"


def test_persisted_status_overrides_other_instances_old_memory_in_both_directions(tmp_path: Path):
    batch = _batch("small_cap_absorption", "小市值", "000001", "样本")
    source_a = FakeSource("small_cap_absorption", "小市值", batch)
    source_b = FakeSource("small_cap_absorption", "小市值", batch)
    database = tmp_path / "hub.db"
    a = CandidateRefreshService(CandidateSnapshotRepository(database), [source_a])
    b = CandidateRefreshService(CandidateSnapshotRepository(database), [source_b])
    assert a.refresh().sources[0].status == "ok"
    source_b.error = "其他实例刷新失败"
    assert b.refresh().sources[0].status == "stale"
    assert a.get_candidates().sources[0].status == "stale"
    assert a.get_candidates().sources[0].error == source_b.error
    assert a.refresh().sources[0].status == "ok"
    assert b.get_candidates().sources[0].status == "ok"


def test_get_candidates_cannot_combine_old_batch_with_cleared_failure(tmp_path: Path, monkeypatch):
    batch = _batch("small_cap_absorption", "小市值", "000001", "旧样本")
    source = FakeSource("small_cap_absorption", "小市值", batch)
    database = tmp_path / "hub.db"
    reader = CandidateSnapshotRepository(database)
    writer = CandidateSnapshotRepository(database)
    reader.save(batch)
    reader.record_failure(source.source_id, "已知失败")
    original_load = reader.load

    def update_between_separate_reads(source_id):
        old = original_load(source_id)
        writer.save(batch.model_copy(update={"items": []}))
        return old

    monkeypatch.setattr(reader, "load", update_between_separate_reads)
    result = CandidateRefreshService(reader, [source]).get_candidates()
    assert not (result.items and result.sources[0].status == "ok")
