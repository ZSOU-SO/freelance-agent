from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.schemas.case import CaseRagResult, CaseRagStatus
from backend.tests.integration.test_case_api import payload


def test_search_reports_empty_library(client) -> None:
    response = client.post(
        "/api/v1/cases/search", json={"requirement_text": "在线刷题"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "empty_library"
    assert response.json()["retrieval_mode"] == "local_bm25"


def test_search_returns_ranked_match_with_score_breakdown(client) -> None:
    client.post("/api/v1/cases", json=payload("CASE-QUIZ"))
    client.post(
        "/api/v1/cases",
        json=payload(
            "CASE-SHOP",
            original_requirement="开发微信支付商城",
            core_features=["支付", "订单"],
        ),
    )

    response = client.post(
        "/api/v1/cases/search",
        json={
            "requirement_text": "开发在线刷题题库",
            "project_type": "web_app",
            "core_features": ["题库", "答题"],
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "matched"
    assert body["matches"][0]["case"]["project_number"] == "CASE-QUIZ"
    assert 0 <= body["matches"][0]["similarity"] <= 1
    assert "text_score" in body["matches"][0]
    assert len(body["matches"]) == 1


def test_search_returns_no_match_below_threshold(client) -> None:
    client.post("/api/v1/cases", json=payload())
    response = client.post(
        "/api/v1/cases/search",
        json={"requirement_text": "量子卫星轨道计算", "min_similarity": 0.9},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_match"


def test_search_validates_top_k(client) -> None:
    assert (
        client.post(
            "/api/v1/cases/search",
            json={"requirement_text": "刷题", "top_k": 0},
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/cases/search",
            json={"requirement_text": "刷题", "top_k": 11},
        ).status_code
        == 422
    )


class FailingSearchService:
    def search(self, query):
        return CaseRagResult(
            status=CaseRagStatus.FAILED,
            error="RuntimeError: historical case retrieval failed",
        )


def test_search_failure_returns_503_with_unified_body(test_settings) -> None:
    with TestClient(
        create_app(test_settings, case_search_service=FailingSearchService())
    ) as client:
        response = client.post(
            "/api/v1/cases/search", json={"requirement_text": "刷题"}
        )

    assert response.status_code == 503
    assert response.json()["status"] == "failed"


def test_health_distinguishes_empty_and_ready_case_library(client) -> None:
    empty = client.get("/api/v1/health").json()
    client.post("/api/v1/cases", json=payload())
    ready = client.get("/api/v1/health").json()

    assert empty["case_library"]["status"] == "empty"
    assert ready["case_library"]["status"] == "ready"

