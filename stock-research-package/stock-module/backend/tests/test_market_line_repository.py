import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.domain.market_lines import MarketEnvironment, MarketLineSnapshot
from app.repositories.market_lines import MarketLineHistoryRepository


GENERATED_AT = datetime(2026, 9, 24, 16, 0, tzinfo=timezone.utc)


def _snapshot(day: int, *, label: str = "中性") -> MarketLineSnapshot:
    return MarketLineSnapshot(
        status="fresh",
        as_of_date=date(2026, 8, 1) + timedelta(days=day - 1),
        generated_at=GENERATED_AT,
        source="同花顺",
        market_environment=MarketEnvironment(
            label=label, advancing=500, declining=500, flat=100, limit_up_count=30,
        ),
        hot_concept_ranks={"机器人": 1},
        lines=[],
    )


def test_history_repository_replaces_same_date_and_sorts_snapshots(tmp_path) -> None:
    repository = MarketLineHistoryRepository(tmp_path / "market-line-history.json")

    repository.save(_snapshot(3, label="偏弱"))
    repository.save(_snapshot(1))
    repository.save(_snapshot(3, label="偏强"))

    history = repository.load()
    assert [item.as_of_date for item in history] == [date(2026, 8, 1), date(2026, 8, 3)]
    assert history[-1].market_environment.label == "偏强"


def test_history_repository_keeps_only_latest_sixty_sessions(tmp_path) -> None:
    repository = MarketLineHistoryRepository(tmp_path / "market-line-history.json")

    for session in range(1, 63):
        repository.save(_snapshot(session))

    history = repository.load()
    assert len(history) == 60
    assert [item.as_of_date for item in history] == [
        date(2026, 8, 1) + timedelta(days=session - 1)
        for session in range(3, 63)
    ]


@pytest.mark.parametrize(
    "snapshot",
    [
        MarketLineSnapshot(
            status="unavailable",
            as_of_date=None,
            generated_at=None,
            source=None,
            market_environment=MarketEnvironment(label="暂无数据"),
        ),
        MarketLineSnapshot(
            status="stale",
            as_of_date=date(2026, 8, 2),
            generated_at=GENERATED_AT,
            source="同花顺",
            market_environment=MarketEnvironment(label="暂无数据"),
        ),
    ],
)
def test_history_repository_rejects_unusable_snapshots_without_overwriting(
    tmp_path, snapshot: MarketLineSnapshot,
) -> None:
    path = tmp_path / "market-line-history.json"
    repository = MarketLineHistoryRepository(path)
    repository.save(_snapshot(1))
    previous = path.read_bytes()

    with pytest.raises(ValueError):
        repository.save(snapshot)

    assert path.read_bytes() == previous
    assert not path.with_suffix(".json.tmp").exists()


def test_history_repository_writes_parseable_json_atomically(tmp_path) -> None:
    path = tmp_path / "market-line-history.json"
    repository = MarketLineHistoryRepository(path)

    repository.save(_snapshot(1))

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload[0]["as_of_date"] == "2026-08-01"
    assert repository.load()[0].as_of_date == date(2026, 8, 1)
    assert not path.with_suffix(".json.tmp").exists()
