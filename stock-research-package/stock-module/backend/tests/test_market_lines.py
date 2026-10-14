from datetime import date, datetime, timezone

from app.domain.market_lines import (
    ConceptMarketInput,
    ConceptMarketMember,
    MarketEnvironment,
    MarketLineSnapshot,
    build_limitup_ladder,
    classify_market_environment,
    score_market_lines,
)


AS_OF = date(2026, 9, 24)
GENERATED_AT = datetime(2026, 9, 24, 16, 0, tzinfo=timezone.utc)


def _stock_row(symbol: str, name: str, boards: int, *, offset: int = 0) -> dict[str, object]:
    bars = []
    for index in range(boards):
        close = 10.0 + offset + index
        bars.append({
            "date": f"2026-09-{25 - boards + index}",
            "open": close - 0.5,
            "high": close,
            "low": close - 0.8,
            "close": close,
            "pct": 10.0,
            "volume": 1_000_000,
        })
    if boards < 3:
        prior_close = 10.0 + offset
        bars.insert(0, {
            "date": f"2026-09-{24 - boards}",
            "open": prior_close,
            "high": prior_close + 0.2,
            "low": prior_close - 0.2,
            "close": prior_close,
            "pct": 0.5,
            "volume": 500_000,
        })
        bars = bars[-(boards + 1):]
    return {
        "symbol": symbol,
        "name": name,
        "market_cap": 5_000_000_000,
        "bars": bars,
    }


def _concept(
    name: str = "机器人",
    *,
    hot_rank: int = 1,
    pct: float = 4.0,
    turnover: float = 100.0,
    up: int = 70,
    down: int = 30,
    symbols: tuple[str, ...] = ("600001", "000002"),
) -> ConceptMarketInput:
    return ConceptMarketInput(
        name=name,
        code=f"{hot_rank:06d}",
        hot_rank=hot_rank,
        pct=pct,
        turnover_yi=turnover,
        up_count=up,
        down_count=down,
        members=[
            ConceptMarketMember(symbol=symbol, name=f"样本{symbol}", pct=10.0)
            for symbol in symbols
        ],
    )


def _history(
    *top_ten_names: str,
    as_of_date: date = date(2026, 9, 23),
) -> MarketLineSnapshot:
    return MarketLineSnapshot(
        status="fresh",
        as_of_date=as_of_date,
        generated_at=GENERATED_AT,
        source="同花顺",
        market_environment=MarketEnvironment(
            label="中性", advancing=500, declining=500, flat=100, limit_up_count=30,
        ),
        hot_concept_ranks={name: rank for rank, name in enumerate(top_ten_names, 1)},
        lines=[],
    )


def test_build_limitup_ladder_counts_mainboard_tiers_and_coverage() -> None:
    members = [
        ConceptMarketMember(symbol=symbol, name=name, pct=10.0)
        for symbol, name in (
            ("600001", "三板样本"),
            ("000002", "二板样本甲"),
            ("600003", "二板样本乙"),
            ("000004", "首板样本甲"),
            ("600005", "首板样本乙"),
            ("000006", "首板样本丙"),
            ("300007", "创业板排除"),
            ("688008", "科创板排除"),
        )
    ]
    rows = [
        _stock_row("600001", "三板样本", 3),
        _stock_row("000002", "二板样本甲", 2),
        _stock_row("600003", "二板样本乙", 2, offset=2),
        _stock_row("000004", "首板样本甲", 1),
        _stock_row("600005", "首板样本乙", 1, offset=2),
        _stock_row("000006", "首板样本丙", 1, offset=4),
        _stock_row("300007", "创业板排除", 3),
        _stock_row("688008", "科创板排除", 3),
    ]

    tiers, leaders, known_bars, eligible_members, eligible_symbols = build_limitup_ladder(members, rows, AS_OF)

    assert tiers == {"first_board": 3, "second_board": 2, "three_plus_board": 1}
    assert [leader.symbol for leader in leaders] == [
        "600001", "000002", "600003", "000004", "000006", "600005",
    ]
    assert known_bars == 6
    assert eligible_members == 6
    assert eligible_symbols == ["600001", "000002", "600003", "000004", "600005", "000006"]


def test_build_limitup_ladder_does_not_count_missing_latest_bars() -> None:
    members = [
        ConceptMarketMember(symbol="600001", name="新鲜样本", pct=10.0),
        ConceptMarketMember(symbol="000002", name="旧样本", pct=10.0),
    ]
    rows = [
        _stock_row("600001", "新鲜样本", 1),
        {
            **_stock_row("000002", "旧样本", 1),
            "bars": [{
                "date": "2026-09-23", "open": 10.0, "high": 11.0,
                "low": 9.8, "close": 11.0, "pct": 10.0, "volume": 100,
            }],
        },
    ]

    tiers, leaders, known_bars, eligible_members, eligible_symbols = build_limitup_ladder(members, rows, AS_OF)

    assert tiers == {"first_board": 1, "second_board": 0, "three_plus_board": 0}
    assert [leader.symbol for leader in leaders] == ["600001"]
    assert known_bars == 1
    assert eligible_members == 2
    assert eligible_symbols == ["600001"]


def test_build_limitup_ladder_accepts_datetime_bar_dates() -> None:
    row = _stock_row("600001", "带时间样本", 1)
    row["bars"][0]["date"] = datetime(2026, 9, 24, 16, 0)

    tiers, leaders, known_bars, eligible_members, eligible_symbols = build_limitup_ladder(
        [ConceptMarketMember(symbol="600001", name="带时间样本", pct=10.0)],
        [row],
        AS_OF,
    )

    assert tiers["first_board"] == 1
    assert [leader.symbol for leader in leaders] == ["600001"]
    assert known_bars == eligible_members == 1
    assert eligible_symbols == ["600001"]


def test_market_environment_uses_mainboard_breadth_thresholds() -> None:
    assert classify_market_environment(39, 61) == "偏弱"
    assert classify_market_environment(40, 60) == "中性"
    assert classify_market_environment(60, 40) == "偏强"
    assert classify_market_environment(0, 0) == "暂无数据"


def test_score_market_lines_confirms_persistent_theme_with_ladder() -> None:
    concept = _concept(up=70, down=30)
    rows = [
        _stock_row("600001", "三板样本", 3),
        _stock_row("000002", "二板样本", 2),
    ]
    history = [
        _history("机器人", as_of_date=date(2026, 9, 22)),
        _history("机器人", "风电", as_of_date=date(2026, 9, 23)),
    ]
    environment = MarketEnvironment(
        label="偏弱", advancing=30, declining=70, flat=5, limit_up_count=20,
    )

    snapshot = score_market_lines(
        [concept], history, rows, environment, AS_OF, GENERATED_AT,
    )

    assert len(snapshot.lines) == 1
    assert snapshot.lines[0].name == "机器人"
    assert snapshot.lines[0].source_rank == 1
    assert snapshot.lines[0].persistence_count == 3
    assert snapshot.lines[0].label == "持续主线"
    assert snapshot.lines[0].score == round(
        snapshot.lines[0].ladder_score * 0.35
        + snapshot.lines[0].breadth_score * 0.25
        + snapshot.lines[0].persistence_count * 20 * 0.25
        + snapshot.lines[0].activity_score * 0.15,
        2,
    )
    assert snapshot.hot_concept_ranks == {"机器人": 1}


def test_score_market_lines_separates_candidate_from_fast_rotation() -> None:
    concept = _concept(
        hot_rank=1,
        up=90,
        down=10,
        symbols=("600001", "000002", "600003", "000004", "600005", "000006"),
    )
    rows = [
        _stock_row("600001", "三板一", 3),
        _stock_row("000002", "三板二", 3, offset=3),
        _stock_row("600003", "二板一", 2),
        _stock_row("000004", "二板二", 2, offset=3),
        _stock_row("600005", "首板一", 1),
        _stock_row("000006", "首板二", 1, offset=3),
    ]
    environment = MarketEnvironment(
        label="中性", advancing=50, declining=50, flat=0, limit_up_count=10,
    )
    candidate = score_market_lines(
        [concept], [_history("机器人")], rows, environment, AS_OF, GENERATED_AT,
    ).lines[0]
    rotating_concept = concept.model_copy(update={"hot_rank": 11})
    rotating = score_market_lines(
        [rotating_concept], [], rows, environment, AS_OF, GENERATED_AT,
    ).lines[0]

    assert candidate.score >= 60
    assert candidate.persistence_count == 2
    assert candidate.label == "主线候选"
    assert rotating.score >= 60
    assert rotating.persistence_count == 0
    assert rotating.label == "快速轮动"


def test_score_market_lines_returns_only_five_composite_ranked_themes() -> None:
    concepts = [
        _concept(name=f"主题{rank}", hot_rank=rank, pct=rank, turnover=rank * 10)
        for rank in range(1, 8)
    ]
    environment = MarketEnvironment(
        label="中性", advancing=50, declining=50, flat=0, limit_up_count=10,
    )

    snapshot = score_market_lines(concepts, [], [], environment, AS_OF, GENERATED_AT)

    assert len(snapshot.lines) == 5
    assert [line.name for line in snapshot.lines] == [f"主题{rank}" for rank in range(7, 2, -1)]
    assert snapshot.hot_concept_ranks == {f"主题{rank}": rank for rank in range(1, 8)}


def test_persistence_counts_real_sessions_and_treats_missing_snapshots_as_absent() -> None:
    concept = _concept(hot_rank=11)
    rows = [{
        "symbol": "600001",
        "name": "测试样本",
        "market_cap": 5e9,
        "bars": [
            {
                "date": date(2026, 9, day).isoformat(),
                "open": 10.0,
                "high": 10.1,
                "low": 9.9,
                "close": 10.0,
                "pct": 0.0,
                "volume": 1000,
            }
            for day in range(18, 25)
        ],
    }]
    history = [
        _history("机器人", as_of_date=date(2026, 9, 19)),
        _history("机器人", as_of_date=date(2026, 9, 22)),
        _history("机器人", as_of_date=date(2026, 9, 23)),
    ]
    environment = MarketEnvironment(
        label="中性", advancing=50, declining=50, flat=0, limit_up_count=10,
    )

    snapshot = score_market_lines(
        [concept], history, rows, environment, AS_OF, GENERATED_AT,
    )

    assert snapshot.lines[0].persistence_count == 2
