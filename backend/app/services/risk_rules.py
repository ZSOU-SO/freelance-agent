from __future__ import annotations

import re

from backend.app.schemas.common import RiskCategory, RiskItem, RiskSeverity


_RISK_RULES: tuple[
    tuple[RiskCategory, RiskSeverity, tuple[str, ...], str], ...
] = (
    (
        RiskCategory.PAYMENT,
        RiskSeverity.HIGH,
        (r"验收.{0,6}(后|以后).{0,4}(付款|结款)", r"完成.{0,6}(后|以后).{0,4}(付款|结款)", r"先做后付"),
        "付款节点偏后，存在回款风险",
    ),
    (
        RiskCategory.HARDWARE,
        RiskSeverity.HIGH,
        (r"硬件", r"蓝牙", r"串口", r"打印机", r"传感器", r"设备联调"),
        "涉及硬件或设备联调，环境与样机可能影响进度",
    ),
    (
        RiskCategory.THIRD_PARTY_PLATFORM,
        RiskSeverity.MEDIUM,
        (r"微信支付", r"支付宝", r"抖音", r"开放平台", r"第三方", r"API\b", r"接口对接"),
        "依赖第三方平台、资质或接口稳定性",
    ),
    (
        RiskCategory.URGENT_DELIVERY,
        RiskSeverity.HIGH,
        (r"紧急", r"加急", r"必须.{0,5}上线", r"[1-7一二三四五六七]天(内|上线|交付)"),
        "交付周期紧张，需要压缩排期并控制范围",
    ),
)


def detect_risks(text: str) -> list[RiskItem]:
    risks: list[RiskItem] = []
    for category, severity, patterns, reason in _RISK_RULES:
        evidence = next(
            (match.group(0) for pattern in patterns if (match := re.search(pattern, text, re.IGNORECASE))),
            None,
        )
        if evidence:
            risks.append(
                RiskItem(
                    category=category,
                    severity=severity,
                    reason=reason,
                    evidence=evidence,
                )
            )
    return risks

