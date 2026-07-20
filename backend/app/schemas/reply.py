from __future__ import annotations

from pydantic import Field

from backend.app.schemas.common import StrictModel
from backend.app.schemas.quote import QuoteAgentOutput
from backend.app.schemas.requirement import RequirementAgentOutput
from backend.app.schemas.technical import TechnicalAgentOutput


class ReplyAgentInput(StrictModel):
    requirement: RequirementAgentOutput
    technical: TechnicalAgentOutput
    quote: QuoteAgentOutput


class ReplyAgentOutput(StrictModel):
    follow_up_questions: list[str] = Field(default_factory=list)
    client_reply: str = Field(min_length=1)
    recommendation_summary: str = Field(min_length=1)

