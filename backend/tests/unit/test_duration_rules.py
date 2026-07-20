from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


def test_duration_combines_project_and_unique_features() -> None:
    service = DurationService(PricingService.from_file("backend/pricing_rules.json").rules)
    result = service.estimate("web_app", ["payment", "payment"], urgent=False)
    assert (result.min_days, result.max_days) == (15, 25)


def test_urgent_duration_is_compressed_but_positive() -> None:
    service = DurationService(PricingService.from_file("backend/pricing_rules.json").rules)
    result = service.estimate("web_app", ["payment"], urgent=True)
    assert (result.min_days, result.max_days) == (12, 19)
    assert "紧急" in result.explanation
