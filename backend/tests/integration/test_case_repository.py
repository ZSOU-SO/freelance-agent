import json
import uuid

import pytest

from backend.app.persistence.case_repository import (
    CaseConflictError,
    CaseDataError,
    CaseRepository,
)
from backend.app.persistence.database import connect, initialize_database
from backend.app.schemas.case import CaseListQuery, HistoricalCaseCreate


def make_case(project_number: str, **overrides) -> HistoricalCaseCreate:
    payload = {
        "project_number": project_number,
        "project_type": "web_app",
        "original_requirement": f"{project_number} 在线刷题系统",
        "core_features": ["题库管理", "在线答题"],
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
        "lessons_learned": "尽早确认题目格式",
    }
    payload.update(overrides)
    return HistoricalCaseCreate.model_validate(payload)


@pytest.fixture
def repository(tmp_path) -> CaseRepository:
    path = tmp_path / "cases.sqlite3"
    initialize_database(path)
    return CaseRepository(path)


def test_repository_crud_round_trip(repository: CaseRepository) -> None:
    created = repository.create(make_case("CASE-001"))

    uuid.UUID(created.id)
    assert repository.get(created.id) == created
    assert repository.get_by_project_number("case-001") == created

    updated = repository.update(
        created.id,
        make_case(
            "CASE-001",
            client_budget=None,
            lessons_learned="更新后的经验",
        ),
    )
    assert updated is not None
    assert updated.created_at == created.created_at
    assert updated.updated_at >= created.updated_at
    assert updated.client_budget is None
    assert updated.lessons_learned == "更新后的经验"

    assert repository.delete(created.id) is True
    assert repository.delete(created.id) is False
    assert repository.get(created.id) is None


def test_repository_lists_and_filters_stably(repository: CaseRepository) -> None:
    first = repository.create(make_case("CASE-001"))
    second = repository.create(
        make_case(
            "CASE-002",
            project_type="mini_program",
            original_requirement="微信支付商城",
            core_features=["支付", "订单"],
            is_won=False,
            final_deal_price=None,
            actual_duration_days=None,
        )
    )

    all_cases = repository.list(CaseListQuery(limit=10, offset=0))
    mini_programs = repository.list(
        CaseListQuery(project_type="mini_program", is_won=False, q="支付")
    )

    assert all_cases.total == 2
    assert [item.id for item in all_cases.items] == [second.id, first.id]
    assert [item.project_number for item in mini_programs.items] == ["CASE-002"]


def test_repository_maps_duplicate_number_to_conflict(repository: CaseRepository) -> None:
    repository.create(make_case("CASE-001"))

    with pytest.raises(CaseConflictError):
        repository.create(make_case("case-001"))


def test_repository_skips_corrupt_rows_in_lists_but_detail_raises(
    repository: CaseRepository,
) -> None:
    valid = repository.create(make_case("CASE-001"))
    corrupt_id = str(uuid.uuid4())
    with connect(repository.database_path) as connection:
        source = connection.execute(
            "SELECT * FROM historical_cases WHERE id = ?", (valid.id,)
        ).fetchone()
        values = dict(source)
        values["id"] = corrupt_id
        values["project_number"] = "CASE-BAD"
        values["core_features_json"] = "not-json"
        columns = ", ".join(values)
        placeholders = ", ".join("?" for _ in values)
        connection.execute(
            f"INSERT INTO historical_cases ({columns}) VALUES ({placeholders})",
            tuple(values.values()),
        )

    result = repository.list(CaseListQuery())
    corpus = repository.list_for_retrieval()

    assert [item.id for item in result.items] == [valid.id]
    assert result.warnings
    assert [item.id for item in corpus.items] == [valid.id]
    assert corpus.warnings
    with pytest.raises(CaseDataError):
        repository.get(corrupt_id)

