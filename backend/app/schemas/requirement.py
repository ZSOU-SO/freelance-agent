from __future__ import annotations

from pydantic import Field, field_validator

from backend.app.schemas.common import BudgetRange, DurationEstimate, StrictModel


class RequirementAgentInput(StrictModel):
    requirement_text: str = Field(min_length=1, max_length=20_000)

    @field_validator("requirement_text")
    @classmethod
    def strip_and_validate(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("requirement_text cannot be blank")
        return value


class RequirementAgentOutput(StrictModel):
    project_type: str = Field(min_length=1)
    features: list[str] = Field(default_factory=list)
    client_budget: BudgetRange | None = None
    desired_deadline: DurationEstimate | None = None
    risk_signals: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)

