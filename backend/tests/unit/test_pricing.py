import json

import pytest

from backend.app.schemas.common import RiskCategory, RiskItem, RiskSeverity
from backend.app.schemas.requirement import RequirementAgentOutput
from backend.app.services.pricing import PricingRulesError, PricingService


@pytest.fixture
def pricing_service() -> PricingService:
    return PricingService.from_file("backend/pricing_rules.json")


def test_pricing_uses_base_features_and_urgent_multiplier(
    pricing_service: PricingService,
) -> None:
    requirement = RequirementAgentOutput(project_type="web_app", features=["payment"])
    risks = [
        RiskItem(
            category=RiskCategory.URGENT_DELIVERY,
            severity=RiskSeverity.HIGH,
            reason="客户要求三天上线",
        )
    ]

    result = pricing_service.calculate(requirement, risks)

    assert result.currency == "CNY"
    assert result.min_amount == 24_000
    assert result.max_amount == 42_000
    assert [item.code for item in result.calculation_items] == [
        "base:web_app",
        "feature:payment",
        "risk:urgent_delivery",
    ]


def test_pricing_deduplicates_features_and_applies_payment_risk(
    pricing_service: PricingService,
) -> None:
    requirement = RequirementAgentOutput(
        project_type="website",
        features=["authentication", "authentication"],
    )
    risks = [
        RiskItem(
            category=RiskCategory.PAYMENT,
            severity=RiskSeverity.HIGH,
            reason="验收后才付款",
        )
    ]

    result = pricing_service.calculate(requirement, risks)

    assert [item.code for item in result.calculation_items].count(
        "feature:authentication"
    ) == 1
    assert "risk:payment" in {item.code for item in result.calculation_items}
    assert "risk:payment_high" in {item.code for item in result.calculation_items}


def test_unknown_project_type_uses_other_rules(pricing_service: PricingService) -> None:
    result = pricing_service.calculate(
        RequirementAgentOutput(project_type="custom_ai", features=[]), []
    )
    assert result.calculation_items[0].code == "base:other"


def test_invalid_currency_is_rejected(tmp_path) -> None:
    rules = json.loads(open("backend/pricing_rules.json", encoding="utf-8").read())
    rules["currency"] = "USD"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(rules), encoding="utf-8")

    with pytest.raises(PricingRulesError, match="CNY"):
        PricingService.from_file(path)

