from __future__ import annotations

import math

from backend.app.schemas.common import (
    DurationEstimate,
    AcceptanceVerdict,
    Recommendation,
    RiskCategory,
    RiskItem,
    RiskSeverity,
)
from backend.app.schemas.technical import (
    TechnicalAgentInput,
    TechnicalAgentOutput,
    TechnicalSolution,
)
from backend.app.services.duration_rules import DurationService


_RISK_DETAILS = {
    RiskCategory.PAYMENT: (
        RiskSeverity.HIGH,
        "付款节点偏后，建议设置预付款和里程碑付款",
    ),
    RiskCategory.HARDWARE: (
        RiskSeverity.HIGH,
        "硬件联调依赖样机、驱动和现场环境",
    ),
    RiskCategory.THIRD_PARTY_PLATFORM: (
        RiskSeverity.MEDIUM,
        "第三方平台资质、审核和接口变更可能影响进度",
    ),
    RiskCategory.URGENT_DELIVERY: (
        RiskSeverity.HIGH,
        "紧急交付需要冻结范围并预留加急成本",
    ),
}


class LocalTechnicalExecutor:
    def __init__(self, duration_service: DurationService):
        self.duration_service = duration_service

    async def execute(self, stage_input: TechnicalAgentInput) -> TechnicalAgentOutput:
        requirement = stage_input.requirement
        risk_categories = [
            RiskCategory(value)
            for value in requirement.risk_signals
            if value in RiskCategory._value2member_map_
        ]
        risks = [
            RiskItem(
                category=category,
                severity=_RISK_DETAILS[category][0],
                reason=_RISK_DETAILS[category][1],
            )
            for category in dict.fromkeys(risk_categories)
        ]
        existing_categories = {risk.category for risk in risks}
        for category in stage_input.case_insight.known_risks:
            if category not in existing_categories:
                risks.append(
                    RiskItem(
                        category=category,
                        severity=_RISK_DETAILS[category][0],
                        reason=f"历史相似案例提示：{_RISK_DETAILS[category][1]}",
                    )
                )
                existing_categories.add(category)
        urgent = RiskCategory.URGENT_DELIVERY in risk_categories
        duration = self.duration_service.estimate(
            requirement.project_type, requirement.features, urgent=urgent
        )
        adjustment = stage_input.case_insight.duration_adjustment_percent
        if adjustment:
            duration = DurationEstimate(
                min_days=duration.min_days,
                max_days=max(
                    duration.min_days,
                    math.ceil(duration.max_days * (1 + adjustment / 100)),
                ),
                explanation=(
                    f"{duration.explanation}；依据历史案例将最大工期上调 {adjustment}%"
                ),
                raw_text=duration.raw_text,
            )

        integrations: list[str] = []
        if "payment" in requirement.features:
            integrations.append("支付平台 API")
        if "hardware_integration" in requirement.features:
            integrations.append("硬件设备协议")
        if "third_party_integration" in requirement.features:
            integrations.append("第三方开放平台")

        high_risk_count = sum(risk.severity == RiskSeverity.HIGH for risk in risks)
        if high_risk_count >= 3:
            verdict = AcceptanceVerdict.REJECT
            should_accept = False
            reasons = ["高风险条件叠加，当前范围和交付承诺不可控"]
        elif risks:
            verdict = AcceptanceVerdict.CONDITIONAL
            should_accept = True
            reasons = ["技术可实现，但需先确认风险边界和里程碑"]
        else:
            verdict = AcceptanceVerdict.ACCEPT
            should_accept = True
            reasons = ["技术路线清晰，当前未识别到重大交付风险"]

        return TechnicalAgentOutput(
            solution=TechnicalSolution(
                frontend=["Vue 3", "TypeScript"],
                backend=["Python", "FastAPI"],
                database=["SQLite"],
                deployment=["Docker", "反向代理"],
                integrations=integrations,
                architecture="前后端分离，后端按领域服务和流水线执行器分层",
                deliverables=["前端源代码", "后端源代码", "数据库脚本", "部署文档"],
            ),
            estimated_duration=duration,
            risks=risks,
            recommendation=Recommendation(
                should_accept=should_accept,
                verdict=verdict,
                reasons=reasons,
            ),
            case_impacts=[
                {
                    "agent": "TechnicalAgent",
                    "project_number": project_number,
                    "summary": (
                        f"参考历史案例校准技术风险和工期"
                        + (f"，最大工期上调 {adjustment}%" if adjustment else "")
                    ),
                }
                for project_number in stage_input.case_insight.source_project_numbers
            ],
        )
