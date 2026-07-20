from dataclasses import dataclass
from typing import Any

from backend.app.schemas.quote import PricingCalculation, QuoteAgentInput, QuoteAgentOutput
from backend.app.services.pricing import PricingService


@dataclass
class QuoteRunContext:
    stage_input: QuoteAgentInput
    pricing: PricingCalculation | None = None


def build_quote_agent(
    pricing_service: PricingService, model: str | None = None
) -> Any:
    from agents import Agent, ModelSettings, RunContextWrapper, function_tool

    @function_tool(name_override="calculate_quote")
    async def calculate_quote(ctx: RunContextWrapper[QuoteRunContext]) -> str:
        """Calculate the authoritative local quote for the validated stage input."""
        ctx.context.pricing = pricing_service.calculate(
            ctx.context.stage_input.requirement,
            ctx.context.stage_input.technical.risks,
        )
        return ctx.context.pricing.model_dump_json()

    return Agent[QuoteRunContext](
        name="QuoteAgent",
        instructions=(
            "你是报价说明专家。必须先调用 calculate_quote。最终结构中的 pricing 必须"
            "原样复制工具结果；你只能补充报价解释、假设和付款节点，不得修改金额或币种。"
        ),
        model=model,
        tools=[calculate_quote],
        model_settings=ModelSettings(tool_choice="calculate_quote"),
        reset_tool_choice=True,
        output_type=QuoteAgentOutput,
    )
