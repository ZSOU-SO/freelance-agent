from __future__ import annotations

from backend.app.schemas.quote import QuoteAgentInput, QuoteAgentOutput
from backend.app.services.pricing import PricingService


class LocalQuoteExecutor:
    def __init__(self, pricing_service: PricingService):
        self.pricing_service = pricing_service

    async def execute(self, stage_input: QuoteAgentInput) -> QuoteAgentOutput:
        pricing = self.pricing_service.calculate(
            stage_input.requirement, stage_input.technical.risks
        )
        return QuoteAgentOutput(
            pricing=pricing,
            explanation="报价由本地报价规则按项目基础价、功能项和风险系数计算。",
            assumptions=[
                "报价为人民币税前区间",
                "需求范围以当前已识别功能为准",
                "第三方服务费、硬件采购费和平台手续费不包含在开发报价中",
            ],
            payment_terms="建议 40% 预付款、40% 阶段验收款、20% 最终交付款",
        )

