from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import Field, field_validator, model_validator

from backend.app.schemas.common import (
    BudgetRange,
    DurationEstimate,
    RiskCategory,
    RiskItem,
    StrictModel,
)


MoneyRange = BudgetRange
DurationRange = DurationEstimate


class CaseRagStatus(str, Enum):
    NOT_RUN = "not_run"
    MATCHED = "matched"
    EMPTY_LIBRARY = "empty_library"
    NO_MATCH = "no_match"
    FAILED = "failed"


class HistoricalCaseFields(StrictModel):
    project_number: str = Field(min_length=3, max_length=64)
    project_type: str = Field(min_length=1, max_length=100)
    original_requirement: str = Field(min_length=1, max_length=20_000)
    core_features: list[str] = Field(min_length=1)
    client_budget: MoneyRange | None = None
    suggested_quote: MoneyRange
    final_deal_price: int | None = Field(default=None, ge=0)
    estimated_duration: DurationRange
    actual_duration_days: int | None = Field(default=None, gt=0)
    risks: list[RiskItem] = Field(default_factory=list)
    is_won: bool
    lessons_learned: str = Field(min_length=1, max_length=5_000)

    @field_validator("project_number")
    @classmethod
    def normalize_project_number(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9._-]{3,64}", normalized):
            raise ValueError("project_number contains unsupported characters")
        return normalized

    @field_validator("project_type")
    @classmethod
    def normalize_project_type(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("project_type cannot be blank")
        return normalized

    @field_validator("original_requirement", "lessons_learned")
    @classmethod
    def strip_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("text cannot be blank")
        return normalized

    @field_validator("core_features")
    @classmethod
    def normalize_features(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for value in values:
            normalized = value.strip()
            key = normalized.casefold()
            if normalized and key not in seen:
                seen.add(key)
                result.append(normalized)
        if not result:
            raise ValueError("core_features must contain at least one value")
        return result

    @field_validator("risks")
    @classmethod
    def deduplicate_risks(cls, values: list[RiskItem]) -> list[RiskItem]:
        result: list[RiskItem] = []
        seen: set[str] = set()
        for value in values:
            key = value.model_dump_json()
            if key not in seen:
                seen.add(key)
                result.append(value)
        return result

    @model_validator(mode="after")
    def validate_outcome_fields(self) -> "HistoricalCaseFields":
        if self.is_won and self.final_deal_price is None:
            raise ValueError("won cases require final_deal_price")
        if not self.is_won and self.final_deal_price is not None:
            raise ValueError("lost cases cannot have final_deal_price")
        if not self.is_won and self.actual_duration_days is not None:
            raise ValueError("lost cases cannot have actual_duration_days")
        return self


class HistoricalCaseCreate(HistoricalCaseFields):
    pass


class HistoricalCaseUpdate(HistoricalCaseFields):
    pass


class HistoricalCaseSummary(StrictModel):
    id: str = Field(min_length=1)
    project_number: str = Field(min_length=3)
    project_type: str = Field(min_length=1)
    core_features: list[str]
    client_budget: MoneyRange | None = None
    suggested_quote: MoneyRange
    final_deal_price: int | None = Field(default=None, ge=0)
    estimated_duration: DurationRange
    actual_duration_days: int | None = Field(default=None, gt=0)
    risks: list[RiskItem] = Field(default_factory=list)
    is_won: bool
    lessons_learned: str = Field(min_length=1)
    created_at: datetime


class HistoricalCaseRead(HistoricalCaseFields):
    id: str = Field(min_length=1)
    created_at: datetime
    updated_at: datetime

    def to_summary(self) -> HistoricalCaseSummary:
        return HistoricalCaseSummary.model_validate(
            self.model_dump(exclude={"original_requirement", "updated_at"})
        )


class HistoricalCaseListResponse(StrictModel):
    items: list[HistoricalCaseRead]
    total: int = Field(ge=0)
    limit: int = Field(gt=0)
    offset: int = Field(ge=0)
    warnings: list[str] = Field(default_factory=list)


class CaseListQuery(StrictModel):
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    project_type: str | None = None
    is_won: bool | None = None
    q: str | None = None


class AgentCaseImpact(StrictModel):
    agent: Literal["TechnicalAgent", "QuoteAgent"]
    project_number: str = Field(min_length=3)
    summary: str = Field(min_length=1)


class SimilarCaseMatch(StrictModel):
    case: HistoricalCaseSummary
    similarity: float = Field(ge=0, le=1)
    text_score: float = Field(default=0, ge=0, le=1)
    feature_score: float = Field(default=0, ge=0, le=1)
    project_type_score: float = Field(default=0, ge=0, le=1)
    risk_score: float = Field(default=0, ge=0, le=1)
    matched_signals: list[str] = Field(default_factory=list)
    matched_terms: list[str] = Field(default_factory=list)
    used_by_agents: list[str] = Field(default_factory=list)
    impacts: list[AgentCaseImpact] = Field(default_factory=list)


class CaseInsight(StrictModel):
    duration_adjustment_percent: int = Field(default=0, ge=0, le=20)
    known_risks: list[RiskCategory] = Field(default_factory=list)
    technical_notes: list[str] = Field(default_factory=list)
    quote_context_notes: list[str] = Field(default_factory=list)
    source_project_numbers: list[str] = Field(default_factory=list)


class CaseSearchRequest(StrictModel):
    requirement_text: str = Field(min_length=1, max_length=20_000)
    project_type: str | None = None
    core_features: list[str] = Field(default_factory=list)
    risk_categories: list[RiskCategory] = Field(default_factory=list)
    top_k: int = Field(default=5, ge=1, le=10)
    min_similarity: float = Field(default=0.25, ge=0, le=1)


class CaseRagResult(StrictModel):
    status: CaseRagStatus = CaseRagStatus.NOT_RUN
    retrieval_mode: str = "local_bm25"
    min_similarity: float = Field(default=0.25, ge=0, le=1)
    matches: list[SimilarCaseMatch] = Field(default_factory=list)
    used_by_agents: list[str] = Field(default_factory=list)
    impact_summary: list[str] = Field(default_factory=list)
    candidate_count: int = Field(default=0, ge=0)
    highest_similarity: float | None = Field(default=None, ge=0, le=1)
    warning: str | None = None
    error: str | None = None

