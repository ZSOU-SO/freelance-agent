from __future__ import annotations

from backend.app.persistence.case_repository import CaseRepository
from backend.app.retrieval.base import (
    CaseRetrievalProvider,
    CaseSearchQuery,
)
from backend.app.schemas.case import (
    CaseRagResult,
    CaseRagStatus,
    SimilarCaseMatch,
)


class CaseSearchService:
    def __init__(
        self,
        repository: CaseRepository,
        provider: CaseRetrievalProvider,
    ) -> None:
        self.repository = repository
        self.provider = provider

    def search(self, query: CaseSearchQuery) -> CaseRagResult:
        try:
            corpus = self.repository.list_for_retrieval()
            if not corpus.items:
                return CaseRagResult(
                    status=CaseRagStatus.EMPTY_LIBRARY,
                    retrieval_mode=self.provider.name,
                    min_similarity=query.min_similarity,
                    warning="; ".join(corpus.warnings) or None,
                )
            scored = self.provider.search(query, corpus.items)
            highest = scored[0].similarity if scored else None
            eligible = [
                item for item in scored if item.similarity >= query.min_similarity
            ][: query.top_k]
            if not eligible:
                return CaseRagResult(
                    status=CaseRagStatus.NO_MATCH,
                    retrieval_mode=self.provider.name,
                    min_similarity=query.min_similarity,
                    candidate_count=len(corpus.items),
                    highest_similarity=highest,
                    warning="; ".join(corpus.warnings) or None,
                )
            return CaseRagResult(
                status=CaseRagStatus.MATCHED,
                retrieval_mode=self.provider.name,
                min_similarity=query.min_similarity,
                matches=[
                    SimilarCaseMatch(
                        case=item.case.to_summary(),
                        similarity=item.similarity,
                        text_score=item.text_score,
                        feature_score=item.feature_score,
                        project_type_score=item.project_type_score,
                        risk_score=item.risk_score,
                        matched_signals=item.matched_signals,
                        matched_terms=item.matched_terms,
                    )
                    for item in eligible
                ],
                candidate_count=len(corpus.items),
                highest_similarity=highest,
                warning="; ".join(corpus.warnings) or None,
            )
        except Exception as exc:
            return CaseRagResult(
                status=CaseRagStatus.FAILED,
                retrieval_mode=self.provider.name,
                min_similarity=query.min_similarity,
                error=f"{type(exc).__name__}: historical case retrieval failed",
            )

