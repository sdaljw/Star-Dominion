from datetime import date, datetime, timezone
import json
from pathlib import Path

import httpx
import pytest
from cryptography.fernet import Fernet

from app.config import Settings
from app.domain.market_lines import MarketEnvironment, MarketLineSnapshot
from app.main import create_app
from app.repositories.market_lines import MarketLineHistoryRepository


GENERATED_AT = datetime(2026, 9, 24, 16, 0, tzinfo=timezone.utc)


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        catalyst_report_path=tmp_path / "catalyst.json",
        user_strategy_snapshot_path=tmp_path / "strategy" / "latest.json",
        model_master_key=Fernet.generate_key().decode("ascii"),
    )


def _snapshot() -> MarketLineSnapshot:
    return MarketLineSnapshot(
        status="fresh",
        as_of_date=date(2026, 9, 24),
        generated_at=GENERATED_AT,
        source="同花顺",
        market_environment=MarketEnvironment(
            label="偏强", advancing=700, declining=300, flat=20, limit_up_count=50,
        ),
        hot_concept_ranks={"机器人": 1},
        lines=[],
    )


def _write_latest(
    path: Path,
    *,
    day: str,
    status: str = "ok",
    generated_at: str = "2026-09-24T16:00:00+08:00",
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "small_cap_status": status,
        "small_cap_generated_at": generated_at,
        "small_cap_stocks": [{"bars": [{"date": day}]}],
    }), encoding="utf-8")


@pytest.mark.asyncio
async def test_market_line_api_returns_fresh_when_history_matches_latest_market_data(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    MarketLineHistoryRepository(settings.user_strategy_snapshot_path.with_name("market-line-history.json")).save(_snapshot())
    _write_latest(settings.user_strategy_snapshot_path, day="2026-09-24")
    application = create_app(settings=settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/market-line/current")

    assert response.status_code == 200
    assert response.json()["status"] == "fresh"
    assert response.json()["as_of_date"] == "2026-09-24"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("latest_day", "small_cap_status", "generated_at"),
    [("2026-09-25", "ok", "2026-09-25T16:00:00+08:00"),
     ("2026-09-24", "error", "2026-09-24T16:00:00+08:00"),
     ("2026-09-24", "ok", "2026-09-24T14:00:00+08:00")],
)
async def test_market_line_api_marks_snapshot_stale_when_sources_do_not_match(
    tmp_path: Path, latest_day: str, small_cap_status: str, generated_at: str,
) -> None:
    settings = _settings(tmp_path)
    MarketLineHistoryRepository(settings.user_strategy_snapshot_path.with_name("market-line-history.json")).save(_snapshot())
    _write_latest(
        settings.user_strategy_snapshot_path,
        day=latest_day,
        status=small_cap_status,
        generated_at=generated_at,
    )
    application = create_app(settings=settings)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/market-line/current")

    assert response.status_code == 200
    assert response.json()["status"] == "stale"
    assert response.json()["as_of_date"] == "2026-09-24"


@pytest.mark.asyncio
async def test_market_line_api_returns_unavailable_without_history(tmp_path: Path) -> None:
    application = create_app(settings=_settings(tmp_path))

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application), base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/market-line/current")

    assert response.status_code == 200
    assert response.json()["status"] == "unavailable"
    assert response.json()["market_environment"]["label"] == "暂无数据"
