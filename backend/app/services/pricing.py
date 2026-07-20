from __future__ import annotations

import json
import math
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from backend.app.schemas.common import RiskCategory, RiskItem, RiskSeverity
from backend.app.schemas.quote import CalculationItem, PricingCalculation
from backend.app.schemas.requirement import RequirementAgentOutput


class PricingRulesError(ValueError):
    """Raised when local pricing rules are invalid."""


class AmountRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    min_amount: int = Field(ge=0)
    max_amount: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_range(self) -> "AmountRule":
        if self.min_amount > self.max_amount:
            raise ValueError("min_amount must not exceed max_amount")
        return self


class ProjectRule(AmountRule):
    min_days: int = Field(gt=0)
    max_days: int = Field(gt=0)


class FeatureRule(ProjectRule):
    pass


class MultiplierRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    multiplier: float = Field(gt=0)


class PricingRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    currency: str
    rounding_unit: int = Field(gt=0)
    project_types: dict[str, ProjectRule]
    features: dict[str, FeatureRule]
    risk_fees: dict[str, AmountRule]
    risk_multipliers: dict[str, MultiplierRule]

    @model_validator(mode="after")
    def validate_required_rules(self) -> "PricingRules":
        if self.currency != "CNY":
            raise ValueError("pricing currency must be CNY")
        if "other" not in self.project_types:
            raise ValueError("project_types must define other")
        return self


class PricingService:
    def __init__(self, rules: PricingRules):
        self.rules = rules

    @classmethod
    def from_file(cls, path: str | Path) -> "PricingService":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
            return cls(PricingRules.model_validate(data))
        except (OSError, json.JSONDecodeError, ValidationError) as exc:
            raise PricingRulesError(f"Invalid pricing rules: {exc}") from exc

    def calculate(
        self,
        requirement: RequirementAgentOutput,
        risks: list[RiskItem],
    ) -> PricingCalculation:
        project_key = (
            requirement.project_type
            if requirement.project_type in self.rules.project_types
            else "other"
        )
        project = self.rules.project_types[project_key]
        minimum = project.min_amount
        maximum = project.max_amount
        items = [
            CalculationItem(
                code=f"base:{project_key}",
                label=project.label,
                kind="base",
                min_amount=project.min_amount,
                max_amount=project.max_amount,
            )
        ]

        for feature_key in dict.fromkeys(requirement.features):
            feature = self.rules.features.get(feature_key)
            if feature is None:
                continue
            minimum += feature.min_amount
            maximum += feature.max_amount
            items.append(
                CalculationItem(
                    code=f"feature:{feature_key}",
                    label=feature.label,
                    kind="addition",
                    min_amount=feature.min_amount,
                    max_amount=feature.max_amount,
                )
            )

        risks_by_category = {risk.category: risk for risk in risks}
        for category, risk in risks_by_category.items():
            fee = self.rules.risk_fees.get(category.value)
            if fee is not None:
                minimum += fee.min_amount
                maximum += fee.max_amount
                items.append(
                    CalculationItem(
                        code=f"risk:{category.value}",
                        label=fee.label,
                        kind="addition",
                        min_amount=fee.min_amount,
                        max_amount=fee.max_amount,
                    )
                )

            multiplier_key = category.value
            if category == RiskCategory.PAYMENT and risk.severity == RiskSeverity.HIGH:
                multiplier_key = "payment_high"
            multiplier = self.rules.risk_multipliers.get(multiplier_key)
            if multiplier is not None:
                minimum *= multiplier.multiplier
                maximum *= multiplier.multiplier
                items.append(
                    CalculationItem(
                        code=f"risk:{multiplier_key}",
                        label=multiplier.label,
                        kind="multiplier",
                        multiplier=multiplier.multiplier,
                    )
                )

        unit = self.rules.rounding_unit
        minimum = math.floor(minimum / unit) * unit
        maximum = math.ceil(maximum / unit) * unit
        return PricingCalculation(
            min_amount=int(minimum),
            max_amount=int(maximum),
            currency="CNY",
            calculation_items=items,
        )

