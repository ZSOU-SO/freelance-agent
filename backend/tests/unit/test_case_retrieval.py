from datetime import datetime, timedelta, timezone

import pytest

from backend.app.retrieval.base import CaseSearchQuery, EmbeddingProvider
from backend.app.retrieval.bm25_provider import LocalBm25CaseRetrievalProvider
from backend.app.retrieval.tokenizer import CaseTokenizer
from backend.app.schemas.case import HistoricalCaseRead


def make_case(
    number: str,
    requirement: str,
    features: list[str],
    project_type: str = "web_app",
    *,
    created_offset: int = 0,
) -> HistoricalCaseRead:
    created = datetime(2026, 7, 21, tzinfo=timezone.utc) + timedelta(
        seconds=created_offset
    )
    return HistoricalCaseRead.model_validate(
        {
            "id": f"id-{number}",
            "project_number": number,
            "project_type": project_type,
            "original_requirement": requirement,
            "core_features": features,
            "client_budget": None,
            "suggested_quote": {
                "min_amount": 10_000,
                "max_amount": 20_000,
                "currency": "CNY",
            },
            "final_deal_price": None,
            "estimated_duration": {
                "min_days": 10,
                "max_days": 15,
                "explanation": "估算",
            },
            "actual_duration_days": None,
            "risks": [],
            "is_won": False,
            "lessons_learned": "需求边界要尽早确认",
            "created_at": created,
            "updated_at": created,
        }
    )


def test_tokenizer_normalizes_chinese_and_technical_terms() -> None:
    tokenizer = CaseTokenizer()

    compact = tokenizer.tokenize("开发一个微信支付 API，使用 VUE3 + FastAPI")
    spaced = tokenizer.tokenize("开发一个微 信，支 付 api 使用 vue3 + fastapi")

    assert {"微信", "信支", "支付", "api", "vue3", "fastapi"} <= set(compact)
    assert set(compact) == set(spaced)
    assert "开发" not in compact


def test_bm25_ranks_matching_case_first_and_scores_are_bounded() -> None:
    provider = LocalBm25CaseRetrievalProvider()
    corpus = [
        make_case("CASE-QUIZ", "Vue3 在线刷题 Web 应用和题库", ["题库管理", "在线答题"]),
        make_case("CASE-SHOP", "微信支付商城订单系统", ["支付", "订单"]),
        make_case("CASE-HW", "门禁硬件串口采集", ["硬件", "串口"]),
    ]
    query = CaseSearchQuery(
        requirement_text="做一个 Web 在线刷题题库",
        project_type="web_app",
        core_features=["题库管理", "在线答题"],
    )

    ranked = provider.search(query, corpus)

    assert ranked[0].case.project_number == "CASE-QUIZ"
    assert all(0 <= item.similarity <= 1 for item in ranked)
    assert ranked[0].feature_score == 1
    assert "project_type" in ranked[0].matched_signals


def test_retrieval_handles_empty_and_single_document_corpora() -> None:
    provider = LocalBm25CaseRetrievalProvider()
    query = CaseSearchQuery(requirement_text="刷题")

    assert provider.search(query, []) == []
    result = provider.search(
        query, [make_case("CASE-ONE", "刷题工具", ["答题"])]
    )
    assert len(result) == 1
    assert 0 <= result[0].text_score <= 1


def test_ties_use_feature_then_recency_then_project_number() -> None:
    provider = LocalBm25CaseRetrievalProvider()
    query = CaseSearchQuery(
        requirement_text="完全无关文本", core_features=["共同功能"]
    )
    corpus = [
        make_case("CASE-B", "另一个文本", ["共同功能"], created_offset=0),
        make_case("CASE-C", "另一个文本", ["共同功能"], created_offset=10),
        make_case("CASE-A", "另一个文本", ["共同功能"], created_offset=10),
    ]

    first = provider.search(query, corpus)
    second = provider.search(query, list(reversed(corpus)))

    assert [item.case.project_number for item in first] == [
        "CASE-A",
        "CASE-C",
        "CASE-B",
    ]
    assert [item.model_dump() for item in first] == [
        item.model_dump() for item in second
    ]


def test_embedding_provider_is_only_an_extension_protocol() -> None:
    assert hasattr(EmbeddingProvider, "embed")

