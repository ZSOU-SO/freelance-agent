from __future__ import annotations

import re

from backend.app.schemas.common import BudgetRange, DurationEstimate
from backend.app.schemas.requirement import RequirementAgentInput, RequirementAgentOutput
from backend.app.services.risk_rules import detect_risks


_PROJECT_PATTERNS = (
    ("mini_program", ("小程序", "miniprogram")),
    ("ecommerce", ("商城", "电商", "购物车", "商品下单")),
    ("mobile_app", ("android", "ios", "app", "移动应用")),
    ("automation", ("自动化", "爬虫", "脚本", "机器人")),
    ("web_app", ("web 应用", "web应用", "后台系统", "管理系统", "saas")),
    ("website", ("官网", "企业网站", "展示网站", "网站")),
)

_FEATURE_PATTERNS = {
    "authentication": ("登录", "注册", "用户认证", "权限"),
    "admin_panel": ("管理后台", "后台管理", "运营后台"),
    "payment": ("支付", "付款", "收款"),
    "content_management": ("内容管理", "文章", "新闻", "cms"),
    "realtime_chat": ("聊天", "即时通信", "实时消息", "客服"),
    "hardware_integration": ("硬件", "蓝牙", "打印机", "传感器", "串口"),
    "third_party_integration": ("微信", "支付宝", "抖音", "开放平台", "第三方", "接口对接"),
}


def _amount_to_cny(number: str, unit: str | None) -> int:
    value = float(number)
    if unit == "万":
        value *= 10_000
    elif unit == "千":
        value *= 1_000
    return int(value)


def _extract_budget(text: str) -> BudgetRange | None:
    range_match = re.search(
        r"(?:预算|报价)?\s*(\d+(?:\.\d+)?)\s*(?:到|至|[-~—])\s*(\d+(?:\.\d+)?)\s*(万|千|元)",
        text,
        re.IGNORECASE,
    )
    if range_match:
        minimum, maximum, unit = range_match.groups()
        return BudgetRange(
            min_amount=_amount_to_cny(minimum, unit),
            max_amount=_amount_to_cny(maximum, unit),
            raw_text=range_match.group(0),
        )
    single_match = re.search(
        r"预算\s*(?:约|大概|不超过|控制在)?\s*(\d+(?:\.\d+)?)\s*(万|千|元)",
        text,
        re.IGNORECASE,
    )
    if single_match:
        amount = _amount_to_cny(single_match.group(1), single_match.group(2))
        return BudgetRange(
            min_amount=int(amount * 0.9),
            max_amount=amount,
            raw_text=single_match.group(0),
        )
    return None


def _extract_deadline(text: str) -> DurationEstimate | None:
    match = re.search(r"(\d+)\s*(个?工作日|天|周|个月|月)(?:内|左右|上线|交付)?", text)
    if not match:
        chinese_numbers = {
            "一": 1,
            "二": 2,
            "两": 2,
            "三": 3,
            "四": 4,
            "五": 5,
            "六": 6,
            "七": 7,
            "八": 8,
            "九": 9,
            "十": 10,
        }
        chinese_match = re.search(
            r"([一二两三四五六七八九十])\s*(天|周|个月|月)(?:内|左右|上线|交付)?",
            text,
        )
        if not chinese_match:
            return None
        amount = chinese_numbers[chinese_match.group(1)]
        unit = chinese_match.group(2)
        days = amount * 5 if unit == "周" else amount * 22 if "月" in unit else amount
        return DurationEstimate(
            min_days=days,
            max_days=days,
            explanation="客户明确的目标交付时间",
            raw_text=chinese_match.group(0),
        )
    amount = int(match.group(1))
    unit = match.group(2)
    if "周" in unit:
        days = amount * 5
    elif "月" in unit:
        days = amount * 22
    else:
        days = amount
    return DurationEstimate(
        min_days=days,
        max_days=days,
        explanation="客户明确的目标交付时间",
        raw_text=match.group(0),
    )


class LocalRequirementExecutor:
    async def execute(
        self, stage_input: RequirementAgentInput
    ) -> RequirementAgentOutput:
        text = stage_input.requirement_text
        lowered = text.lower()
        project_type = next(
            (
                project
                for project, keywords in _PROJECT_PATTERNS
                if any(keyword in lowered for keyword in keywords)
            ),
            "other",
        )
        features = [
            feature
            for feature, keywords in _FEATURE_PATTERNS.items()
            if any(keyword in lowered for keyword in keywords)
        ]
        budget = _extract_budget(text)
        deadline = _extract_deadline(text)
        risks = detect_risks(text)
        missing: list[str] = []
        if not features:
            missing.append("请补充核心功能和使用流程。")
        if budget is None:
            missing.append("请确认可接受的预算区间。")
        if deadline is None:
            missing.append("请确认期望上线时间。")
        missing.append("请确认部署环境及验收标准。")
        return RequirementAgentOutput(
            project_type=project_type,
            features=features,
            client_budget=budget,
            desired_deadline=deadline,
            risk_signals=[risk.category.value for risk in risks],
            missing_information=list(dict.fromkeys(missing)),
        )
