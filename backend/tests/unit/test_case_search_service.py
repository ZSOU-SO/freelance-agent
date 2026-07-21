from datetime import datetime, timezone

from backend.app.persistence.case_repository import CaseRetrievalCorpus
from backend.app.retrieval.base import CaseSearchQuery, ScoredCase
from backend.app.retrieval.service import CaseSearchService
from backend.app.schemas.case import CaseRagStatus, HistoricalCaseRead


def case() -> HistoricalCaseRead:
    return HistoricalCaseRead.model_validate(
        {
            "id": "case-id",
            "project_number": "CASE-001",
            "project_type": "web_app",
            "original_requirement": "在线刷题题库",
            "core_features": ["题库管理"],
            "suggested_quote": {
                "min_amount": 1,
                "max_amount": 2,
                "currency": "CNY",
            },
            "final_deal_price": None,
            "estimated_duration": {
                "min_days": 1,
                "max_days": 2,
                "explanation": "估算",
            },
            "actual_duration_days": None,
            "risks": [],
            "is_won": False,
            "lessons_learned": "确认格式",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )


class StubRepository:
    def __init__(self, items=None, warnings=None):
        self.corpus = CaseRetrievalCorpus(
            items=list(items or []), warnings=list(warnings or [])
        )

    def list_for_retrieval(self):
        return self.corpus


class StubProvider:
    name = "local_bm25"

    def __init__(self, scores=None, error=None):
        self.scores = list(scores or [])
        self.error = error

    def search(self, query, corpus):
        if self.error:
            raise self.error
        return self.scores


def score(value: float) -> ScoredCase:
    return ScoredCase(
        case=case(),
        similarity=value,
        text_score=value,
        feature_score=0,
        project_type_score=0,
        risk_score=0,
        matched_terms=["题库"],
    )


def test_empty_case_library_is_not_an_error() -> None:
    result = CaseSearchService(StubRepository(), StubProvider()).search(
        CaseSearchQuery(requirement_text="刷题")
    )

    assert result.status == CaseRagStatus.EMPTY_LIBRARY
    assert result.error is None
    assert result.candidate_count == 0


def test_low_similarity_returns_no_match_with_highest_score() -> None:
    item = case()
    result = CaseSearchService(
        StubRepository([item]), StubProvider([score(0.2)])
    ).search(CaseSearchQuery(requirement_text="刷题", min_similarity=0.25))

    assert result.status == CaseRagStatus.NO_MATCH
    assert result.matches == []
    assert result.highest_similarity == 0.2
    assert result.candidate_count == 1


def test_search_filters_top_k_and_keeps_repository_warning() -> None:
    item = case()
    result = CaseSearchService(
        StubRepository([item], ["Skipped invalid case bad-id"]),
        StubProvider([score(0.9), score(0.8)]),
    ).search(CaseSearchQuery(requirement_text="刷题", top_k=1))

    assert result.status == CaseRagStatus.MATCHED
    assert len(result.matches) == 1
    assert result.warning == "Skipped invalid case bad-id"


def test_provider_error_is_sanitized() -> None:
    fake_key = "sk-" + "placeholder123456789"
    result = CaseSearchService(
        StubRepository([case()]),
        StubProvider(error=RuntimeError(f"failed with {fake_key} at C:/private")),
    ).search(CaseSearchQuery(requirement_text="刷题"))

    assert result.status == CaseRagStatus.FAILED
    assert "placeholder" not in (result.error or "")
    assert result.matches == []
