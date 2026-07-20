from __future__ import annotations

from typing import Any

from backend.app.schemas.requirement import RequirementAgentOutput


def build_requirement_agent(model: str | None = None) -> Any:
    from agents import Agent

    return Agent(
        name="RequirementAgent",
        instructions=(
            "你是外包需求分析专家。只根据输入文本提取项目类型、标准功能、预算、"
            "工期、风险信号和缺失信息。未知信息保持为空，不得猜测。"
        ),
        model=model,
        output_type=RequirementAgentOutput,
    )

