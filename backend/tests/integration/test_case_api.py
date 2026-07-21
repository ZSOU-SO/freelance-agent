from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.persistence.migrations import Migration, MigrationRunner


def payload(number: str = "CASE-001", **overrides):
    value = {
        "project_number": number,
        "project_type": "web_app",
        "original_requirement": "开发在线刷题网站",
        "core_features": ["题库", "答题"],
        "client_budget": None,
        "suggested_quote": {
            "min_amount": 10_000,
            "max_amount": 20_000,
            "currency": "CNY",
        },
        "final_deal_price": 15_000,
        "estimated_duration": {
            "min_days": 10,
            "max_days": 15,
            "explanation": "标准工期",
        },
        "actual_duration_days": 16,
        "risks": [],
        "is_won": True,
        "lessons_learned": "先确定题目格式",
    }
    value.update(overrides)
    return value


def test_case_crud_api_round_trip(client) -> None:
    created = client.post("/api/v1/cases", json=payload())
    assert created.status_code == 201
    case = created.json()

    detail = client.get(f"/api/v1/cases/{case['id']}")
    listed = client.get("/api/v1/cases?page=1&page_size=10&q=刷题")
    assert detail.status_code == 200
    assert detail.json() == case
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["id"] == case["id"]

    changed = payload(lessons_learned="更新后的经验")
    updated = client.put(f"/api/v1/cases/{case['id']}", json=changed)
    assert updated.status_code == 200
    assert updated.json()["lessons_learned"] == "更新后的经验"

    deleted = client.delete(f"/api/v1/cases/{case['id']}")
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/cases/{case['id']}").status_code == 404
    assert client.delete(f"/api/v1/cases/{case['id']}").status_code == 404


def test_case_api_maps_duplicate_number_to_409(client) -> None:
    assert client.post("/api/v1/cases", json=payload("CASE-001")).status_code == 201

    response = client.post("/api/v1/cases", json=payload("case-001"))

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "case_project_number_conflict"


def test_case_api_rejects_invalid_outcome(client) -> None:
    response = client.post(
        "/api/v1/cases",
        json=payload(is_won=False, final_deal_price=100, actual_duration_days=2),
    )
    assert response.status_code == 422


def test_case_api_returns_404_for_missing_update(client) -> None:
    response = client.put("/api/v1/cases/missing", json=payload())
    assert response.status_code == 404


def test_case_api_returns_503_when_migration_failed(test_settings) -> None:
    runner = MigrationRunner(
        migrations=(Migration(version="broken", statements=("INVALID SQL",)),)
    )
    with TestClient(create_app(test_settings, migration_runner=runner)) as client:
        response = client.get("/api/v1/cases")

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "case_library_unavailable"

