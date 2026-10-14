"""Candidate refresh orchestration with source-level failure isolation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.candidates import CandidateStock, merge_candidates
from app.integrations.candidate_sources import CandidateProvider
from app.repositories.candidate_snapshots import CandidateSnapshotRepository


class CandidateSourceStatus(BaseModel):
    source_id: str
    source_name: str
    status: Literal["ok", "stale", "error", "not_configured"]
    generated_at: datetime | None = None
    error: str | None = None


class CandidateCollection(BaseModel):
    items: list[CandidateStock] = Field(default_factory=list)
    sources: list[CandidateSourceStatus] = Field(default_factory=list)


class CandidateRefreshService:
    def __init__(
        self,
        repository: CandidateSnapshotRepository,
        sources: list[CandidateProvider],
    ) -> None:
        self._repository = repository
        self._sources = sources

    def refresh(self) -> CandidateCollection:
        for source in self._sources:
            try:
                batch = source.load()
                self._repository.save(batch)
            except Exception as exc:
                self._repository.record_failure(source.source_id, str(exc))
        return self.get_candidates()

    def get_candidates(self) -> CandidateCollection:
        items: list[CandidateStock] = []
        statuses: list[CandidateSourceStatus] = []
        for source in self._sources:
            batch, failure = self._repository.load_state(source.source_id)
            if batch:
                items.extend(batch.items)
            status = CandidateSourceStatus(
                source_id=source.source_id,
                source_name=source.source_name,
                status=("stale" if batch else "error") if failure is not None else ("ok" if batch else "not_configured"),
                generated_at=batch.generated_at if batch else None,
                error=failure,
            )
            statuses.append(status)
        return CandidateCollection(items=merge_candidates(items), sources=statuses)
