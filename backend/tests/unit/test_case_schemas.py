from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.case import (
    CaseRagResult,
    CaseRagStatus,
    HistoricalCaseCreate,
    HistoricalCaseRead,
    SimilarCaseMatch,
)
from backend.app.schemas.common import RiskCategory, RiskSeverity


def valid_case_payload(**overrides):
    payload = {
        "project_number": " fa.2026-001 ",
        "project_type": "web_app",
        "original_requirement": "开发一个 Vue 3 在线刷题 Web 应用",
        "core_features": ["题库管理", "在线答题", "题库管理"],
        "client_budget": {
            "min_amount": 10_000,
            "max_amount": 20_000,
            "currency": "CNY",
        },
        "suggested_quote": {
            "min_amount": 12_000,
            "max_amount": 18_000,
            "currency": "CNY",
        },
        "final_deal_price": 15_000,
        "estimated_duration": {
            "min_days": 10,
            "max_days": 15,
            "explanation": "标准 Web 项目",
        },
        "actual_duration_days": 16,
        "risks": [
            {
                "category": RiskCategory.THIRD_PARTY_PLATFORM,
                "severity": RiskSeverity.MEDIUM,
                "reason": "浏览器兼容",
            },
            {
                "category": RiskCategory.THIRD_PARTY_PLATFORM,
                "severity": RiskSeverity.MEDIUM,
                "reason": "浏览器兼容",
            },
        ],
        "is_won": True,
        "lessons_learned": "题目格式需要尽早确认。",
    }
    payload.update(overrides)
    return payload


def test_case_create_normalizes_number_and_deduplicates_lists() -> None:
    case = HistoricalCaseCreate.model_validate(valid_case_payload())

    assert case.project_number == "FA.2026-001"
    assert case.core_features == ["题库管理", "在线答题"]
    assert len(case.risks) == 1


@pytest.mark.parametrize("project_number", ["ab", "bad number", "编号-001"])
def test_case_create_rejects_invalid_project_number(project_number: str) -> None:
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(
            valid_case_payload(project_number=project_number)
        )


def test_won_case_requires_final_deal_price() -> None:
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(
            valid_case_payload(is_won=True, final_deal_price=None)
        )


def test_lost_case_rejects_deal_price_and_actual_duration() -> None:
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(
            valid_case_payload(is_won=False, final_deal_price=1, actual_duration_days=2)
        )


def test_case_amounts_require_non_negative_integer_cny() -> None:
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(
            valid_case_payload(
                suggested_quote={
                    "min_amount": 1.5,
                    "max_amount": 2_000,
                    "currency": "CNY",
                }
            )
        )
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(
            valid_case_payload(final_deal_price=-1)
        )


def test_case_rag_contract_round_trips() -> None:
    created = HistoricalCaseCreate.model_validate(valid_case_payload())
    stored = HistoricalCaseRead(
        id="550e8400-e29b-41d4-a716-446655440000",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        **created.model_dump(),
    )
    result = CaseRagResult(
        status=CaseRagStatus.MATCHED,
        retrieval_mode="local_bm25",
        min_similarity=0.25,
        matches=[
            SimilarCaseMatch(
                case=stored.to_summary(),
                similarity=0.8123,
                text_score=0.8,
                feature_score=1.0,
                project_type_score=1.0,
                risk_score=0.0,
                matched_signals=["project_type", "feature:题库管理"],
                matched_terms=["题库", "vue"],
                used_by_agents=["TechnicalAgent"],
            )
        ],
        used_by_agents=["TechnicalAgent"],
        impact_summary=["参考历史案例补充工期风险"],
    )

    restored = CaseRagResult.model_validate_json(result.model_dump_json())
    assert restored.matches[0].case.project_number == "FA.2026-001"
    assert restored.matches[0].similarity == pytest.approx(0.8123)

