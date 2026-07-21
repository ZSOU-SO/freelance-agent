from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator

from backend.app.schemas.common import (
    AnalysisMode,
    DurationEstimate,
    ExecutionMode,
    Recommendation,
    RiskItem,
    StrictModel,
)
from backend.app.schemas.case import CaseRagResult
from backend.app.schemas.quote import QuoteResult
from backend.app.schemas.requirement import RequirementAgentOutput
from backend.app.schemas.technical import TechnicalSolution


class AnalysisRequest(StrictModel):
    requirement_text: str = Field(min_length=1, max_length=20_000)

    @field_validator("requirement_text")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("requirement_text cannot be blank")
        return value


class StepTelemetry(StrictModel):
    step: str
    execution_mode: ExecutionMode
    duration_ms: float = Field(ge=0)
    fallback_used: bool
    error: str | None = None
    status: str | None = None
    warning: str | None = None


class PipelineTelemetry(StrictModel):
    total_duration_ms: float = Field(ge=0)
    steps: list[StepTelemetry]


class AnalysisResponse(StrictModel):
    id: str = Field(min_length=1)
    created_at: datetime
    requirement_text: str = Field(min_length=1)
    analysis_mode: AnalysisMode
    fallback_occurred: bool
    requirement: RequirementAgentOutput
    technical_solution: TechnicalSolution
    quote: QuoteResult
    estimated_duration: DurationEstimate
    risks: list[RiskItem]
    recommendation: Recommendation
    follow_up_questions: list[str]
    client_reply: str = Field(min_length=1)
    telemetry: PipelineTelemetry
    case_rag: CaseRagResult = Field(default_factory=CaseRagResult)


class AnalysisListResponse(StrictModel):
    items: list[AnalysisResponse]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)
