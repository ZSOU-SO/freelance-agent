from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from backend.app.schemas.common import RiskItem, StrictModel
from backend.app.schemas.requirement import RequirementAgentOutput
from backend.app.schemas.technical import TechnicalAgentOutput


class CalculationItem(StrictModel):
    code: str = Field(min_length=1)
    label: str = Field(min_length=1)
    kind: Literal["base", "addition", "multiplier"] = "addition"
    min_amount: int = Field(default=0, ge=0)
    max_amount: int = Field(default=0, ge=0)
    multiplier: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def validate_amounts(self) -> "CalculationItem":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount must not exceed max_amount")
        if self.kind == "multiplier" and self.multiplier is None:
            raise ValueError("multiplier items require a multiplier")
        return self


class PricingCalculation(StrictModel):
    min_amount: int = Field(ge=0)
    max_amount: int = Field(ge=0)
    currency: Literal["CNY"] = "CNY"
    calculation_items: list[CalculationItem]

    @model_validator(mode="after")
    def validate_range(self) -> "PricingCalculation":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount must not exceed max_amount")
        return self


class QuoteAgentInput(StrictModel):
    requirement: RequirementAgentOutput
    technical: TechnicalAgentOutput


class QuoteAgentOutput(StrictModel):
    pricing: PricingCalculation
    explanation: str = Field(min_length=1)
    assumptions: list[str] = Field(default_factory=list)
    payment_terms: str = Field(min_length=1)


class QuoteResult(QuoteAgentOutput):
    pass


class PricingToolInput(StrictModel):
    project_type: str
    features: list[str]
    risks: list[RiskItem]

