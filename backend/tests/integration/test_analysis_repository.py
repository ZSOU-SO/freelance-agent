import pytest
import json

from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.persistence.database import connect
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.case import CaseRagStatus


@pytest.mark.asyncio
async def test_repository_round_trips_validated_analysis(test_settings) -> None:
    repository = AnalysisRepository(test_settings.database_path)
    repository.initialize()
    result = await PipelineOrchestrator(settings=test_settings).analyze(
        "开发一个带内容管理的企业官网"
    )

    repository.save(result)

    assert repository.get(result.id) == result
    page = repository.list(limit=10, offset=0)
    assert page.total == 1
    assert page.items == [result]
    assert len(result.telemetry.steps) == 5
    assert repository.get(result.id).case_rag == result.case_rag


def test_repository_returns_none_for_missing_record(test_settings) -> None:
    repository = AnalysisRepository(test_settings.database_path)
    repository.initialize()
    assert repository.get("missing") is None


@pytest.mark.asyncio
async def test_repository_reads_phase_one_json_without_case_rag(test_settings) -> None:
    repository = AnalysisRepository(test_settings.database_path)
    repository.initialize()
    result = await PipelineOrchestrator(settings=test_settings).analyze("开发企业官网")
    payload = result.model_dump(mode="json")
    payload.pop("case_rag")
    payload["telemetry"]["steps"] = [
        step
        for step in payload["telemetry"]["steps"]
        if step["step"] != "case_retrieval"
    ]
    payload["id"] = "phase-one-record"
    with connect(test_settings.database_path) as connection:
        connection.execute(
            "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?)",
            (
                payload["id"],
                payload["requirement_text"],
                json.dumps(payload, ensure_ascii=False),
                payload["analysis_mode"],
                0,
                payload["created_at"],
            ),
        )

    restored = repository.get("phase-one-record")

    assert restored is not None
    assert restored.case_rag.status == CaseRagStatus.NOT_RUN
    assert len(restored.telemetry.steps) == 4


@pytest.mark.asyncio
async def test_repository_list_skips_invalid_analysis_record(test_settings) -> None:
    repository = AnalysisRepository(test_settings.database_path)
    repository.initialize()
    valid = await PipelineOrchestrator(settings=test_settings).analyze("开发企业官网")
    repository.save(valid)
    with connect(test_settings.database_path) as connection:
        connection.execute(
            "INSERT INTO analyses VALUES (?, ?, ?, ?, ?, ?)",
            (
                "bad-record",
                "损坏记录",
                '{"case_rag":{"status":"impossible"}}',
                "local_fallback",
                0,
                valid.created_at.isoformat(),
            ),
        )

    page = repository.list(limit=10, offset=0)

    assert page.items == [valid]
    assert page.total == 2
    assert page.warnings == ["Skipped invalid analysis bad-record"]
