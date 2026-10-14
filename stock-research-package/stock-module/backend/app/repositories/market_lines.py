"""Atomic persistence for daily market-mainline history."""

import json
import os
from pathlib import Path

from app.domain.market_lines import MarketLineSnapshot


MAX_HISTORY_SESSIONS = 60


class MarketLineHistoryRepository:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> list[MarketLineSnapshot]:
        if not self._path.exists():
            return []
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            if not isinstance(payload, list):
                raise ValueError("主线历史必须是 JSON 数组")
            return [MarketLineSnapshot.model_validate(item) for item in payload]
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("主线历史文件无法读取") from exc

    def save(self, snapshot: MarketLineSnapshot) -> None:
        if snapshot.status != "fresh" or snapshot.as_of_date is None or snapshot.generated_at is None:
            raise ValueError("只允许保存日期与生成时间完整的最新主线快照")

        history = {item.as_of_date: item for item in self.load() if item.as_of_date is not None}
        history[snapshot.as_of_date] = snapshot
        retained = sorted(history.values(), key=lambda item: item.as_of_date)[-MAX_HISTORY_SESSIONS:]

        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(
                    [item.model_dump(mode="json") for item in retained],
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            os.replace(temporary, self._path)
        finally:
            if temporary.exists():
                temporary.unlink()
