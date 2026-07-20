import pytest

from backend.app.schemas.common import RiskCategory
from backend.app.services.risk_rules import detect_risks


@pytest.mark.parametrize(
    ("text", "category"),
    [
        ("项目完成并验收以后再付款", RiskCategory.PAYMENT),
        ("需要对接蓝牙打印机硬件", RiskCategory.HARDWARE),
        ("需要接入微信支付和抖音开放平台", RiskCategory.THIRD_PARTY_PLATFORM),
        ("非常紧急，三天内必须上线", RiskCategory.URGENT_DELIVERY),
    ],
)
def test_detects_required_risk_categories(text: str, category: RiskCategory) -> None:
    assert category in {risk.category for risk in detect_risks(text)}


def test_risks_are_deduplicated_by_category() -> None:
    risks = detect_risks("微信支付、支付宝和第三方开放平台都要接入")
    assert [risk.category for risk in risks].count(RiskCategory.THIRD_PARTY_PLATFORM) == 1


def test_normal_request_has_no_rule_risk() -> None:
    assert detect_risks("制作一个包含公司介绍和联系方式的官网") == []

