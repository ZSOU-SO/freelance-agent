from datetime import datetime, timezone

from backend.app.retrieval.insights import CaseInsightService
from backend.app.schemas.case import (
    HistoricalCaseRead,
    SimilarCaseMatch,
)
from backend.app.schemas.common import RiskCategory, RiskSeverity


def match(number: str, actual_days: int | None, similarity: float = 0.8):
    won = actual_days is not None
    stored = HistoricalCaseRead.model_validate(
        {
            "id": f"id-{number}",
            "project_number": number,
            "project_type": "web_app",
            "original_requirement": "刷题工具",
            "core_features": ["题库"],
            "suggested_quote": {
                "min_amount": 10_000,
                "max_amount": 20_000,
                "currency": "CNY",
            },
            "final_deal_price": 15_000 if won else None,
            "estimated_duration": {
                "min_days": 8,
                "max_days": 10,
                "explanation": "估算",
            },
            "actual_duration_days": actual_days,
            "risks": [
                {
                    "category": RiskCategory.THIRD_PARTY_PLATFORM,
                    "severity": RiskSeverity.MEDIUM,
                    "reason": "浏览器限制",
                }
            ],
            "is_won": won,
            "lessons_learned": "先确认数据格式",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return SimilarCaseMatch(
        case=stored.to_summary(),
        similarity=similarity,
        matched_signals=["project_type"],
    )


def test_duration_adjustment_requires_two_completed_won_cases() -> None:
    service = CaseInsightService()

    one = service.summarize([match("CASE-1", 12)])
    two = service.summarize([match("CASE-1", 12), match("CASE-2", 13)])

    assert one.duration_adjustment_percent == 0
    assert two.duration_adjustment_percent == 20
    assert two.source_project_numbers == ["CASE-1", "CASE-2"]


def test_duration_adjustment_does_not_trigger_at_or_below_threshold() -> None:
    insight = CaseInsightService().summarize(
        [match("CASE-1", 11), match("CASE-2", 11)]
    )

    assert insight.duration_adjustment_percent == 0


def test_insights_are_deterministic_and_do_not_contain_quote_fields() -> None:
    service = CaseInsightService()
    matches = [match("CASE-B", 12), match("CASE-A", 12)]

    first = service.summarize(matches)
    second = service.summarize(list(reversed(matches)))

    assert first == second
    assert first.known_risks == [RiskCategory.THIRD_PARTY_PLATFORM]
    assert "suggested_quote" not in type(first).model_fields
    assert "quote_range" not in type(first).model_fields
