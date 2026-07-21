from __future__ import annotations

from pydantic import Field

from backend.app.schemas.case import (
    AgentCaseImpact,
    CaseInsight,
    SimilarCaseMatch,
)
from backend.app.schemas.common import DurationEstimate, Recommendation, RiskItem, StrictModel
from backend.app.schemas.requirement import RequirementAgentOutput


class TechnicalSolution(StrictModel):
    frontend: list[str] = Field(default_factory=list)
    backend: list[str] = Field(default_factory=list)
    database: list[str] = Field(default_factory=list)
    deployment: list[str] = Field(default_factory=list)
    integrations: list[str] = Field(default_factory=list)
    architecture: str = Field(min_length=1)
    deliverables: list[str] = Field(min_length=1)


class TechnicalAgentInput(StrictModel):
    requirement: RequirementAgentOutput
    similar_cases: list[SimilarCaseMatch] = Field(default_factory=list)
    case_insight: CaseInsight = Field(default_factory=CaseInsight)


class TechnicalAgentOutput(StrictModel):
    solution: TechnicalSolution
    estimated_duration: DurationEstimate
    risks: list[RiskItem] = Field(default_factory=list)
    recommendation: Recommendation
    case_impacts: list[AgentCaseImpact] = Field(default_factory=list)
