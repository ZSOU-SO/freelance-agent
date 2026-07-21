from __future__ import annotations

from collections import Counter

from backend.app.schemas.case import CaseInsight, SimilarCaseMatch


class CaseInsightService:
    def summarize(self, matches: list[SimilarCaseMatch]) -> CaseInsight:
        ordered = sorted(matches, key=lambda item: item.case.project_number)
        source_numbers = [item.case.project_number for item in ordered]
        risk_counts = Counter(
            risk.category
            for item in ordered
            for risk in item.case.risks
        )
        known_risks = [
            category
            for category, _ in sorted(
                risk_counts.items(), key=lambda pair: (-pair[1], pair[0].value)
            )
        ]

        eligible = [
            item
            for item in ordered
            if item.case.is_won and item.case.actual_duration_days is not None
        ]
        adjustment = 0
        if len(eligible) >= 2:
            total_weight = sum(item.similarity for item in eligible)
            if total_weight > 0:
                weighted_overrun = sum(
                    max(
                        0.0,
                        (
                            item.case.actual_duration_days
                            - item.case.estimated_duration.max_days
                        )
                        / item.case.estimated_duration.max_days,
                    )
                    * item.similarity
                    for item in eligible
                ) / total_weight
                if weighted_overrun > 0.15:
                    adjustment = min(20, round(weighted_overrun * 100))

        technical_notes: list[str] = []
        if known_risks:
            technical_notes.append(
                "历史案例反复出现风险："
                + "、".join(category.value for category in known_risks)
            )
        if adjustment:
            technical_notes.append(
                f"参考 {len(eligible)} 个已成交案例，建议将最大工期上调 {adjustment}%"
            )

        deal_prices = sorted(
            item.case.final_deal_price
            for item in eligible
            if item.case.final_deal_price is not None
        )
        quote_notes: list[str] = []
        if deal_prices:
            quote_notes.append(
                "历史成交价仅供解释："
                f"{deal_prices[0]} 至 {deal_prices[-1]} CNY；规则报价保持不变"
            )

        return CaseInsight(
            duration_adjustment_percent=adjustment,
            known_risks=known_risks,
            technical_notes=technical_notes,
            quote_context_notes=quote_notes,
            source_project_numbers=source_numbers,
        )

