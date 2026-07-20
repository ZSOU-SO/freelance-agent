from __future__ import annotations

from typing import Any

from backend.app.schemas.reply import ReplyAgentOutput


def build_reply_agent(model: str | None = None) -> Any:
    from agents import Agent

    return Agent(
        name="ReplyAgent",
        instructions=(
            "你是专业的外包商务沟通顾问。依据已经锁定的需求、技术方案、报价、工期和"
            "风险，生成必要追问和可直接发送的中文客户回复。不得改变报价、工期或接单结论。"
        ),
        model=model,
        output_type=ReplyAgentOutput,
    )

