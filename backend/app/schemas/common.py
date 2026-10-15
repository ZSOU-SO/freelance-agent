from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisMode(str, Enum):
    AGENTS = "agents"
    LOCAL_FALLBACK = "local_fallback"


class ExecutionMode(str, Enum):
    AGENT = "agent"
    LOCAL_FALLBACK = "local_fallback"
    LOCAL_RULES = "local_rules"
    LOCAL_RETRIEVAL = "local_retrieval"
    EMBEDDING_RETRIEVAL = "embedding_retrieval"


class RiskCategory(str, Enum):
    PAYMENT = "payment"
    HARDWARE = "hardware"
    THIRD_PARTY_PLATFORM = "third_party_platform"
    URGENT_DELIVERY = "urgent_delivery"


class RiskSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class AcceptanceVerdict(str, Enum):
    ACCEPT = "accept"
    CONDITIONAL = "conditional"
    REJECT = "reject"


class BudgetRange(StrictModel):
    min_amount: int = Field(ge=0)
    max_amount: int = Field(ge=0)
    currency: str = "CNY"
    raw_text: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "BudgetRange":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount must not exceed max_amount")
        return self


class DurationEstimate(StrictModel):
    min_days: int = Field(gt=0)
    max_days: int = Field(gt=0)
    explanation: str = Field(min_length=1)
    raw_text: str | None = None

    @model_validator(mode="after")
    def validate_range(self) -> "DurationEstimate":
        if self.min_days > self.max_days:
            raise ValueError("min_days must not exceed max_days")
        return self


class RiskItem(StrictModel):
    category: RiskCategory
    severity: RiskSeverity
    reason: str = Field(min_length=1)
    evidence: str | None = None


class Recommendation(StrictModel):
    should_accept: bool
    verdict: AcceptanceVerdict
    reasons: list[str] = Field(min_length=1)
