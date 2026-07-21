from __future__ import annotations

import math
from collections import Counter
from typing import Sequence

from backend.app.retrieval.base import CaseSearchQuery, ScoredCase
from backend.app.retrieval.tokenizer import CaseTokenizer
from backend.app.schemas.case import HistoricalCaseRead


class LocalBm25CaseRetrievalProvider:
    name = "local_bm25"

    def __init__(
        self,
        *,
        tokenizer: CaseTokenizer | None = None,
        k1: float = 1.5,
        b: float = 0.75,
    ) -> None:
        self.tokenizer = tokenizer or CaseTokenizer()
        self.k1 = k1
        self.b = b

    def search(
        self,
        query: CaseSearchQuery,
        corpus: Sequence[HistoricalCaseRead],
    ) -> list[ScoredCase]:
        if not corpus:
            return []

        query_tokens = self.tokenizer.tokenize(query.requirement_text)
        documents = [
            self.tokenizer.tokenize(
                f"{case.original_requirement} {case.lessons_learned}"
            )
            for case in corpus
        ]
        average_length = sum(map(len, documents)) / len(documents)
        document_frequency = Counter(
            token for tokens in documents for token in set(tokens)
        )
        query_features = self._normalized_set(query.core_features)
        query_risks = {risk.value for risk in query.risk_categories}

        scored: list[ScoredCase] = []
        for case, tokens in zip(corpus, documents, strict=True):
            raw_text_score = self._bm25(
                query_tokens,
                tokens,
                document_frequency,
                len(documents),
                average_length,
            )
            text_score = raw_text_score / (raw_text_score + 1) if raw_text_score else 0.0
            case_features = self._normalized_set(case.core_features)
            feature_score = self._jaccard(query_features, case_features)
            project_type_score = float(
                bool(query.project_type)
                and query.project_type.strip().casefold()
                == case.project_type.casefold()
            )
            case_risks = {risk.category.value for risk in case.risks}
            risk_score = self._jaccard(query_risks, case_risks)
            similarity = min(
                1.0,
                0.45 * text_score
                + 0.30 * feature_score
                + 0.15 * project_type_score
                + 0.10 * risk_score,
            )
            matched_terms = sorted(set(query_tokens) & set(tokens))
            matched_signals: list[str] = []
            if project_type_score:
                matched_signals.append("project_type")
            matched_signals.extend(
                f"feature:{feature}"
                for feature in sorted(query_features & case_features)
            )
            matched_signals.extend(
                f"risk:{risk}" for risk in sorted(query_risks & case_risks)
            )
            matched_signals.extend(f"text:{term}" for term in matched_terms[:8])
            scored.append(
                ScoredCase(
                    case=case,
                    similarity=similarity,
                    text_score=text_score,
                    feature_score=feature_score,
                    project_type_score=project_type_score,
                    risk_score=risk_score,
                    matched_signals=matched_signals,
                    matched_terms=matched_terms[:12],
                )
            )

        return sorted(
            scored,
            key=lambda item: (
                -item.similarity,
                -item.feature_score,
                -item.case.created_at.timestamp(),
                item.case.project_number,
            ),
        )

    def _bm25(
        self,
        query_tokens: list[str],
        document_tokens: list[str],
        document_frequency: Counter[str],
        document_count: int,
        average_length: float,
    ) -> float:
        if not query_tokens or not document_tokens or average_length <= 0:
            return 0.0
        frequencies = Counter(document_tokens)
        score = 0.0
        for token in set(query_tokens):
            frequency = frequencies[token]
            if not frequency:
                continue
            present_in = document_frequency[token]
            inverse_frequency = math.log(
                1 + (document_count - present_in + 0.5) / (present_in + 0.5)
            )
            denominator = frequency + self.k1 * (
                1 - self.b + self.b * len(document_tokens) / average_length
            )
            score += inverse_frequency * frequency * (self.k1 + 1) / denominator
        return score

    @staticmethod
    def _normalized_set(values: Sequence[str]) -> set[str]:
        return {value.strip().casefold() for value in values if value.strip()}

    @staticmethod
    def _jaccard(left: set[str], right: set[str]) -> float:
        if not left or not right:
            return 0.0
        return len(left & right) / len(left | right)

