from __future__ import annotations

from backend.app.schemas.reply import ReplyAgentInput, ReplyAgentOutput


class LocalReplyExecutor:
    async def execute(self, stage_input: ReplyAgentInput) -> ReplyAgentOutput:
        requirement = stage_input.requirement
        technical = stage_input.technical
        quote = stage_input.quote
        verdict_text = {
            "accept": "建议承接",
            "conditional": "建议在确认风险边界后承接",
            "reject": "暂不建议承接",
        }[technical.recommendation.verdict.value]
        questions = list(dict.fromkeys(requirement.missing_information))
        risk_summary = "；".join(risk.reason for risk in technical.risks) or "暂无明显高风险项"
        client_reply = (
            "您好，感谢您提供项目需求。根据当前信息，我们初步建议采用"
            f"{technical.solution.architecture}。预计工期为 "
            f"{technical.estimated_duration.min_days}–{technical.estimated_duration.max_days} 个工作日，"
            f"开发报价约为 ¥{quote.pricing.min_amount:,}–¥{quote.pricing.max_amount:,}（税前）。"
            f"当前关注点：{risk_summary}。确认补充问题后，我们可以进一步细化范围和里程碑。"
        )
        return ReplyAgentOutput(
            follow_up_questions=questions,
            client_reply=client_reply,
            recommendation_summary=f"{verdict_text}：{technical.recommendation.reasons[0]}",
        )
