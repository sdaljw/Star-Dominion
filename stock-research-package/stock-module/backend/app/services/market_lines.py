"""Read the latest market-mainline snapshot and assess its source freshness."""

from datetime import date, datetime
import json
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.market_lines import MarketEnvironment, MarketLineSnapshot
from app.repositories.market_lines import MarketLineHistoryRepository


class MarketLineService:
    def __init__(
        self,
        repository: MarketLineHistoryRepository,
        latest_snapshot_path: str | Path,
    ) -> None:
        self._repository = repository
        self._latest_snapshot_path = Path(latest_snapshot_path)

    def current(self) -> MarketLineSnapshot:
        try:
            history = self._repository.load()
        except (OSError, ValueError):
            return _unavailable_snapshot()
        if not history:
            return _unavailable_snapshot()

        snapshot = max(
            (item for item in history if item.as_of_date is not None),
            key=lambda item: item.as_of_date,
            default=None,
        )
        if snapshot is None:
            return _unavailable_snapshot()

        latest_payload = _read_json_object(self._latest_snapshot_path)
        latest_date = _latest_small_cap_date(latest_payload)
        generated_at = _small_cap_generated_at(latest_payload)
        is_fresh = (
            latest_payload.get("small_cap_status") == "ok"
            and latest_date is not None
            and latest_date == snapshot.as_of_date
            and generated_at is not None
            and generated_at.date() == snapshot.as_of_date
            and generated_at.hour >= 15
        )
        return snapshot.model_copy(update={"status": "fresh" if is_fresh else "stale"})


def _unavailable_snapshot() -> MarketLineSnapshot:
    return MarketLineSnapshot(
        status="unavailable",
        as_of_date=None,
        generated_at=None,
        source=None,
        market_environment=MarketEnvironment(label="暂无数据"),
        lines=[],
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_small_cap_date(payload: dict[str, Any]) -> date | None:
    rows = payload.get("small_cap_stocks")
    if not isinstance(rows, list):
        return None
    dates: list[date] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("bars"), list):
            continue
        for bar in row["bars"]:
            if not isinstance(bar, dict):
                continue
            value = bar.get("date")
            if not isinstance(value, str):
                continue
            try:
                dates.append(date.fromisoformat(value[:10]))
            except ValueError:
                continue
    return max(dates, default=None)


def _small_cap_generated_at(payload: dict[str, Any]) -> datetime | None:
    value = payload.get("small_cap_generated_at")
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    shanghai = ZoneInfo("Asia/Shanghai")
    return parsed.replace(tzinfo=shanghai) if parsed.tzinfo is None else parsed.astimezone(shanghai)
