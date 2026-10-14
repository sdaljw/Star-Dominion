"""SQLite persistence for the latest successful candidate snapshot per source."""

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

from app.integrations.candidate_sources import CandidateBatch


class CandidateSnapshotRepository:
    def __init__(self, database_path: str | Path) -> None:
        self._path = Path(database_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def save(self, batch: CandidateBatch) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO candidate_snapshots (source_id, payload, generated_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(source_id) DO UPDATE SET
                    payload = excluded.payload,
                    generated_at = excluded.generated_at,
                    updated_at = excluded.updated_at
                """,
                (
                    batch.source_id,
                    batch.model_dump_json(),
                    batch.generated_at.isoformat(),
                    datetime.now(UTC).isoformat(),
                ),
            )
            connection.execute("DELETE FROM candidate_source_failures WHERE source_id = ?", (batch.source_id,))

    def record_failure(self, source_id: str, error: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO candidate_source_failures (source_id, error) VALUES (?, ?) "
                "ON CONFLICT(source_id) DO UPDATE SET error = excluded.error",
                (source_id, error),
            )

    def load_failure(self, source_id: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT error FROM candidate_source_failures WHERE source_id = ?", (source_id,),
            ).fetchone()
        return row[0] if row else None

    def load_state(self, source_id: str) -> tuple[CandidateBatch | None, str | None]:
        # One statement observes payload and failure in the same SQLite read snapshot.
        with self._connect() as connection:
            payload, failure = connection.execute(
                "SELECT (SELECT payload FROM candidate_snapshots WHERE source_id = ?), "
                "(SELECT error FROM candidate_source_failures WHERE source_id = ?)",
                (source_id, source_id),
            ).fetchone()
        return (CandidateBatch.model_validate_json(payload) if payload is not None else None, failure)

    def load(self, source_id: str) -> CandidateBatch | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM candidate_snapshots WHERE source_id = ?",
                (source_id,),
            ).fetchone()
        return CandidateBatch.model_validate_json(row[0]) if row else None

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_snapshots (
                    source_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS candidate_source_failures (source_id TEXT PRIMARY KEY, error TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._path)
