import pytest

from backend.app.executors.local.quote_executor import LocalQuoteExecutor
from backend.app.executors.local.reply_executor import LocalReplyExecutor
from backend.app.executors.local.requirement_executor import LocalRequirementExecutor
from backend.app.executors.local.technical_executor import LocalTechnicalExecutor
from backend.app.schemas.case import CaseInsight
from backend.app.schemas.common import RiskCategory
from backend.app.schemas.quote import QuoteAgentInput
from backend.app.schemas.reply import ReplyAgentInput
from backend.app.schemas.requirement import RequirementAgentInput
from backend.app.schemas.technical import TechnicalAgentInput
from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


@pytest.fixture
def pricing_service() -> PricingService:
    return PricingService.from_file("backend/pricing_rules.json")


@pytest.mark.asyncio
async def test_requirement_executor_extracts_type_features_budget_and_deadline() -> None:
    result = await LocalRequirementExecutor().execute(
        RequirementAgentInput(
            requirement_text="做一个带微信支付的商城，预算3到5万，4周上线"
        )
    )

    assert result.project_type == "ecommerce"
    assert "payment" in result.features
    assert result.client_budget is not None
    assert (result.client_budget.min_amount, result.client_budget.max_amount) == (
        30_000,
        50_000,
    )
    assert result.desired_deadline is not None
    assert result.desired_deadline.max_days == 20
    assert "third_party_platform" in result.risk_signals


@pytest.mark.asyncio
async def test_requirement_executor_extracts_chinese_week_deadline() -> None:
    result = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发微信小程序，预算5万，希望四周上线")
    )

    assert result.desired_deadline is not None
    assert result.desired_deadline.max_days == 20


@pytest.mark.asyncio
async def test_technical_executor_builds_solution_duration_and_risks(
    pricing_service: PricingService,
) -> None:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(
            requirement_text="做一个小程序，需要蓝牙打印机和微信支付，三天内上线"
        )
    )
    executor = LocalTechnicalExecutor(
        DurationService(pricing_service.rules)
    )

    result = await executor.execute(TechnicalAgentInput(requirement=requirement))

    assert "Vue 3" in result.solution.frontend
    assert {risk.category for risk in result.risks} >= {
        RiskCategory.HARDWARE,
        RiskCategory.THIRD_PARTY_PLATFORM,
        RiskCategory.URGENT_DELIVERY,
    }
    assert result.estimated_duration.min_days > 0
    assert result.recommendation.should_accept is True


@pytest.mark.asyncio
async def test_quote_executor_uses_pricing_service(
    pricing_service: PricingService,
) -> None:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发一个带支付的 Web 应用")
    )
    technical = await LocalTechnicalExecutor(
        DurationService(pricing_service.rules)
    ).execute(TechnicalAgentInput(requirement=requirement))

    output = await LocalQuoteExecutor(pricing_service).execute(
        QuoteAgentInput(requirement=requirement, technical=technical)
    )

    assert output.pricing.currency == "CNY"
    assert output.pricing.min_amount < output.pricing.max_amount
    assert "本地报价规则" in output.explanation


@pytest.mark.asyncio
async def test_technical_executor_applies_bounded_case_duration_adjustment(
    pricing_service: PricingService,
) -> None:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发一个 Web 刷题应用")
    )
    executor = LocalTechnicalExecutor(DurationService(pricing_service.rules))
    baseline = await executor.execute(TechnicalAgentInput(requirement=requirement))
    insight = CaseInsight(
        duration_adjustment_percent=20,
        known_risks=[RiskCategory.THIRD_PARTY_PLATFORM],
        technical_notes=["历史案例存在浏览器平台限制"],
        source_project_numbers=["CASE-001", "CASE-002"],
    )

    adjusted = await executor.execute(
        TechnicalAgentInput(requirement=requirement, case_insight=insight)
    )

    assert adjusted.estimated_duration.min_days == baseline.estimated_duration.min_days
    assert adjusted.estimated_duration.max_days <= int(
        baseline.estimated_duration.max_days * 1.2 + 0.999
    )
    assert adjusted.estimated_duration.max_days > baseline.estimated_duration.max_days
    assert {impact.project_number for impact in adjusted.case_impacts} == {
        "CASE-001",
        "CASE-002",
    }
    assert RiskCategory.THIRD_PARTY_PLATFORM in {
        risk.category for risk in adjusted.risks
    }


@pytest.mark.asyncio
async def test_quote_executor_keeps_pricing_authoritative_with_case_context(
    pricing_service: PricingService,
) -> None:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发一个带支付的 Web 应用")
    )
    technical = await LocalTechnicalExecutor(
        DurationService(pricing_service.rules)
    ).execute(TechnicalAgentInput(requirement=requirement))
    expected = pricing_service.calculate(requirement, technical.risks)
    insight = CaseInsight(
        quote_context_notes=["历史成交价为 1 CNY，但规则报价保持不变"],
        source_project_numbers=["CASE-EXTREME"],
    )

    output = await LocalQuoteExecutor(pricing_service).execute(
        QuoteAgentInput(
            requirement=requirement,
            technical=technical,
            case_insight=insight,
        )
    )

    assert output.pricing == expected
    assert "历史成交价" in output.explanation
    assert output.case_impacts[0].project_number == "CASE-EXTREME"


@pytest.mark.asyncio
async def test_reply_executor_uses_locked_quote_and_missing_information(
    pricing_service: PricingService,
) -> None:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发企业官网")
    )
    technical = await LocalTechnicalExecutor(
        DurationService(pricing_service.rules)
    ).execute(TechnicalAgentInput(requirement=requirement))
    quote = await LocalQuoteExecutor(pricing_service).execute(
        QuoteAgentInput(requirement=requirement, technical=technical)
    )

    output = await LocalReplyExecutor().execute(
        ReplyAgentInput(
            requirement=requirement,
            technical=technical,
            quote=quote,
        )
    )

    assert f"¥{quote.pricing.min_amount:,}" in output.client_reply
    assert output.follow_up_questions
    assert "建议" in output.recommendation_summary
