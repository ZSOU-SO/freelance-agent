from types import SimpleNamespace

import pytest

from backend.app.executors.agent_executor import (
    CaseReferenceValidationError,
    QuoteAgentExecutor,
    QuoteToolNotCalledError,
)
from backend.app.schemas.case import AgentCaseImpact, CaseInsight
from backend.app.executors.local.requirement_executor import LocalRequirementExecutor
from backend.app.executors.local.technical_executor import LocalTechnicalExecutor
from backend.app.schemas.quote import PricingCalculation, QuoteAgentInput, QuoteAgentOutput
from backend.app.schemas.requirement import RequirementAgentInput
from backend.app.schemas.technical import TechnicalAgentInput
from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


async def _quote_input(pricing_service: PricingService) -> QuoteAgentInput:
    requirement = await LocalRequirementExecutor().execute(
        RequirementAgentInput(requirement_text="开发带支付的 Web 应用")
    )
    technical = await LocalTechnicalExecutor(
        DurationService(pricing_service.rules)
    ).execute(TechnicalAgentInput(requirement=requirement))
    return QuoteAgentInput(requirement=requirement, technical=technical)


@pytest.mark.asyncio
async def test_quote_agent_requires_local_tool_result() -> None:
    pricing_service = PricingService.from_file("backend/pricing_rules.json")

    async def runner_without_tool(agent, prompt, **kwargs):
        wrong = PricingCalculation(
            min_amount=1,
            max_amount=2,
            currency="CNY",
            calculation_items=[],
        )
        return SimpleNamespace(
            final_output=QuoteAgentOutput(
                pricing=wrong,
                explanation="模型报价",
                assumptions=[],
                payment_terms="全款",
            )
        )

    executor = QuoteAgentExecutor(pricing_service, runner=runner_without_tool)
    assert executor.agent.name == "QuoteAgent"
    assert executor.agent.handoffs == []
    assert [tool.name for tool in executor.agent.tools] == ["calculate_quote"]
    with pytest.raises(QuoteToolNotCalledError):
        await executor.execute(await _quote_input(pricing_service))


@pytest.mark.asyncio
async def test_quote_agent_overrides_model_amounts_with_tool_result() -> None:
    pricing_service = PricingService.from_file("backend/pricing_rules.json")
    quote_input = await _quote_input(pricing_service)

    async def runner_with_tool(agent, prompt, **kwargs):
        context = kwargs["context"]
        context.pricing = pricing_service.calculate(
            context.stage_input.requirement,
            context.stage_input.technical.risks,
        )
        wrong = PricingCalculation(
            min_amount=1,
            max_amount=2,
            currency="CNY",
            calculation_items=[],
        )
        return SimpleNamespace(
            final_output=QuoteAgentOutput(
                pricing=wrong,
                explanation="依据工具结果说明报价",
                assumptions=["范围已确认"],
                payment_terms="40/40/20",
            )
        )

    output = await QuoteAgentExecutor(
        pricing_service, runner=runner_with_tool
    ).execute(quote_input)
    authoritative = pricing_service.calculate(quote_input.requirement, quote_input.technical.risks)

    assert output.pricing == authoritative
    assert output.pricing.min_amount != 1


@pytest.mark.asyncio
async def test_quote_agent_receives_case_context_but_rejects_unknown_reference() -> None:
    pricing_service = PricingService.from_file("backend/pricing_rules.json")
    quote_input = (await _quote_input(pricing_service)).model_copy(
        update={
            "case_insight": CaseInsight(
                quote_context_notes=["历史成交价只用于解释"],
                source_project_numbers=["CASE-001"],
            )
        }
    )
    captured_prompt = ""

    async def runner(agent, prompt, **kwargs):
        nonlocal captured_prompt
        captured_prompt = prompt
        context = kwargs["context"]
        context.pricing = pricing_service.calculate(
            context.stage_input.requirement,
            context.stage_input.technical.risks,
        )
        return SimpleNamespace(
            final_output=QuoteAgentOutput(
                pricing=context.pricing,
                explanation="规则报价",
                assumptions=[],
                payment_terms="40/40/20",
                case_impacts=[
                    AgentCaseImpact(
                        agent="QuoteAgent",
                        project_number="MADE-UP",
                        summary="虚构引用",
                    )
                ],
            )
        )

    executor = QuoteAgentExecutor(pricing_service, runner=runner)
    with pytest.raises(CaseReferenceValidationError):
        await executor.execute(quote_input)

    assert "历史成交价只用于解释" in captured_prompt
    assert "历史案例" in str(executor.agent.instructions)
