from __future__ import annotations

import math

from backend.app.schemas.common import DurationEstimate
from backend.app.services.pricing import PricingRules


class DurationService:
    def __init__(self, rules: PricingRules, urgent_factor: float = 0.75):
        self.rules = rules
        self.urgent_factor = urgent_factor

    def estimate(
        self, project_type: str, features: list[str], *, urgent: bool
    ) -> DurationEstimate:
        project = self.rules.project_types.get(
            project_type, self.rules.project_types["other"]
        )
        minimum = project.min_days
        maximum = project.max_days
        for feature_key in dict.fromkeys(features):
            feature = self.rules.features.get(feature_key)
            if feature:
                minimum += feature.min_days
                maximum += feature.max_days

        if urgent:
            minimum = max(1, math.ceil(minimum * self.urgent_factor))
            maximum = max(minimum, math.ceil(maximum * self.urgent_factor))
            explanation = "按紧急交付条件压缩后的工作日区间，需冻结需求范围"
        else:
            explanation = "按项目类型和已识别功能累加的标准工作日区间"
        return DurationEstimate(
            min_days=minimum,
            max_days=maximum,
            explanation=explanation,
        )
