from __future__ import annotations

from typing import Any

from backend.app.schemas.technical import TechnicalAgentOutput


def build_technical_agent(model: str | None = None) -> Any:
    from agents import Agent

    return Agent(
        name="TechnicalAgent",
        instructions=(
            "你是资深全栈架构师。根据已验证的结构化需求提出可落地的技术方案、"
            "工作日区间、交付物、风险和接单建议。必须覆盖支付、硬件、第三方平台"
            "和紧急交付风险，不得修改上一步需求。"
        ),
        model=model,
        output_type=TechnicalAgentOutput,
    )

