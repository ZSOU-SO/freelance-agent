import pytest

from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.pipeline.orchestrator import PipelineOrchestrator


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


def test_repository_returns_none_for_missing_record(test_settings) -> None:
    repository = AnalysisRepository(test_settings.database_path)
    repository.initialize()
    assert repository.get("missing") is None

