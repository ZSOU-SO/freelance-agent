import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.persistence.database import connect, initialize_database
from backend.app.persistence.migrations import Migration, MigrationRunner


def test_historical_case_migration_is_applied_once(tmp_path) -> None:
    database_path = tmp_path / "cases.sqlite3"

    first = initialize_database(database_path)
    second = initialize_database(database_path)

    assert first.case_library_available is True
    assert second.case_library_available is True
    with connect(database_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        count = connection.execute(
            "SELECT COUNT(*) FROM schema_migrations "
            "WHERE version = '20260721_01_historical_cases'"
        ).fetchone()[0]
    assert {"analyses", "schema_migrations", "historical_cases"} <= tables
    assert count == 1


def test_project_number_is_unique_without_case_sensitivity(tmp_path) -> None:
    database_path = tmp_path / "cases.sqlite3"
    initialize_database(database_path)
    values = (
        "id-1",
        "FA-001",
        "web_app",
        "需求",
        "[]",
        None,
        '{"min_amount":1,"max_amount":2,"currency":"CNY","raw_text":null}',
        None,
        '{"min_days":1,"max_days":2,"explanation":"x","raw_text":null}',
        None,
        "[]",
        0,
        "经验",
        "2026-07-21T00:00:00+00:00",
        "2026-07-21T00:00:00+00:00",
    )
    sql = "INSERT INTO historical_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    with connect(database_path) as connection:
        connection.execute(sql, values)
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(sql, ("id-2", "fa-001", *values[2:]))


def test_failed_migration_rolls_back_version_and_partial_table(tmp_path) -> None:
    database_path = tmp_path / "cases.sqlite3"
    bad_runner = MigrationRunner(
        migrations=(
            Migration(
                version="broken",
                statements=(
                    "CREATE TABLE partial_table (id TEXT PRIMARY KEY)",
                    "THIS IS NOT VALID SQL",
                ),
            ),
        )
    )

    report = initialize_database(database_path, migration_runner=bad_runner)

    assert report.case_library_available is False
    with connect(database_path) as connection:
        partial = connection.execute(
            "SELECT name FROM sqlite_master WHERE name = 'partial_table'"
        ).fetchone()
        version = connection.execute(
            "SELECT version FROM schema_migrations WHERE version = 'broken'"
        ).fetchone()
    assert partial is None
    assert version is None


def test_case_migration_failure_keeps_phase_one_api_available(
    test_settings,
) -> None:
    bad_runner = MigrationRunner(
        migrations=(Migration(version="broken", statements=("INVALID SQL",)),)
    )

    with TestClient(
        create_app(test_settings, migration_runner=bad_runner)
    ) as client:
        health = client.get("/api/v1/health")
        analysis = client.post(
            "/api/v1/analyses", json={"requirement_text": "开发企业官网"}
        )

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.json()["case_library"]["status"] == "degraded"
    assert "INVALID SQL" not in str(health.json())
    assert analysis.status_code == 201

