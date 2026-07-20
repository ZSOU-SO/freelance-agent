from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from backend.app.schemas.analysis import AnalysisResponse, PipelineTelemetry, StepTelemetry
from backend.app.schemas.common import (
    AcceptanceVerdict,
    AnalysisMode,
    BudgetRange,
    DurationEstimate,
    ExecutionMode,
    Recommendation,
    RiskCategory,
    RiskItem,
    RiskSeverity,
)
from backend.app.schemas.quote import CalculationItem, PricingCalculation, QuoteResult
from backend.app.schemas.reply import ReplyAgentOutput
from backend.app.schemas.requirement import RequirementAgentInput, RequirementAgentOutput
from backend.app.schemas.technical import TechnicalAgentOutput, TechnicalSolution


def test_requirement_text_cannot_be_blank() -> None:
    with pytest.raises(ValidationError):
        RequirementAgentInput(requirement_text="   ")


def test_money_and_duration_ranges_reject_reversed_values() -> None:
    with pytest.raises(ValidationError):
        BudgetRange(min_amount=20_000, max_amount=10_000, currency="CNY")
    with pytest.raises(ValidationError):
        DurationEstimate(min_days=20, max_days=10, explanation="bad range")


def test_pricing_calculation_requires_cny() -> None:
    with pytest.raises(ValidationError):
        PricingCalculation(
            min_amount=1_000,
            max_amount=2_000,
            currency="USD",
            calculation_items=[],
        )


def _build_analysis_response(mode: AnalysisMode) -> AnalysisResponse:
    requirement = RequirementAgentOutput(
        project_type="web_app",
        features=["content_management"],
        missing_information=["是否需要部署服务？"],
    )
    technical = TechnicalAgentOutput(
        solution=TechnicalSolution(
            frontend=["Vue 3"],
            backend=["FastAPI"],
            database=["SQLite"],
            deployment=["Docker"],
            integrations=[],
            architecture="前后端分离",
            deliverables=["源代码"],
        ),
        estimated_duration=DurationEstimate(
            min_days=10, max_days=15, explanation="按标准功能估算"
        ),
        risks=[
            RiskItem(
                category=RiskCategory.THIRD_PARTY_PLATFORM,
                severity=RiskSeverity.MEDIUM,
                reason="需确认平台资质",
            )
        ],
        recommendation=Recommendation(
            should_accept=True,
            verdict=AcceptanceVerdict.CONDITIONAL,
            reasons=["需求可控"],
        ),
    )
    pricing = PricingCalculation(
        min_amount=12_000,
        max_amount=20_000,
        currency="CNY",
        calculation_items=[
            CalculationItem(
                code="base:web_app",
                label="Web 应用基础价",
                min_amount=12_000,
                max_amount=20_000,
            )
        ],
    )
    quote = QuoteResult(
        pricing=pricing,
        explanation="依据本地规则计算",
        assumptions=["不含税"],
        payment_terms="40/40/20",
    )
    reply = ReplyAgentOutput(
        follow_up_questions=["请确认部署环境。"],
        client_reply="您好，初步评估可以承接。",
        recommendation_summary="建议有条件承接。",
    )
    telemetry = PipelineTelemetry(
        total_duration_ms=12.5,
        steps=[
            StepTelemetry(
                step="requirement",
                execution_mode=(
                    ExecutionMode.AGENT
                    if mode == AnalysisMode.AGENTS
                    else ExecutionMode.LOCAL_FALLBACK
                ),
                duration_ms=3.1,
                fallback_used=False,
            )
        ],
    )
    return AnalysisResponse(
        id="analysis-1",
        created_at=datetime.now(timezone.utc),
        requirement_text="开发一个后台系统",
        analysis_mode=mode,
        fallback_occurred=False,
        requirement=requirement,
        technical_solution=technical.solution,
        quote=quote,
        estimated_duration=technical.estimated_duration,
        risks=technical.risks,
        recommendation=technical.recommendation,
        follow_up_questions=reply.follow_up_questions,
        client_reply=reply.client_reply,
        telemetry=telemetry,
    )


@pytest.mark.parametrize("mode", [AnalysisMode.AGENTS, AnalysisMode.LOCAL_FALLBACK])
def test_analysis_response_uses_one_contract_for_both_modes(mode: AnalysisMode) -> None:
    response = _build_analysis_response(mode)
    round_trip = AnalysisResponse.model_validate_json(response.model_dump_json())
    assert round_trip.analysis_mode == mode
    assert round_trip.quote.pricing.currency == "CNY"
