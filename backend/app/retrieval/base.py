from __future__ import annotations

from typing import Protocol, Sequence

from pydantic import Field

from backend.app.schemas.case import CaseSearchRequest, HistoricalCaseRead
from backend.app.schemas.common import StrictModel


class CaseSearchQuery(CaseSearchRequest):
    pass


class ScoredCase(StrictModel):
    case: HistoricalCaseRead
    similarity: float = Field(ge=0, le=1)
    text_score: float = Field(ge=0, le=1)
    feature_score: float = Field(ge=0, le=1)
    project_type_score: float = Field(ge=0, le=1)
    risk_score: float = Field(ge=0, le=1)
    matched_signals: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)


class CaseRetrievalProvider(Protocol):
    name: str

    def search(
        self,
        query: CaseSearchQuery,
        corpus: Sequence[HistoricalCaseRead],
    ) -> list[ScoredCase]: ...


class EmbeddingProvider(Protocol):
    name: str

    def embed(
        self, texts: Sequence[str]
    ) -> Sequence[Sequence[float]]: ...

