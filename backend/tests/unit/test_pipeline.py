from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pytest

from backend.app.core.config import Settings
from backend.app.executors.local.quote_executor import LocalQuoteExecutor
from backend.app.executors.local.reply_executor import LocalReplyExecutor
from backend.app.executors.local.requirement_executor import LocalRequirementExecutor
from backend.app.executors.local.technical_executor import LocalTechnicalExecutor
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.case import (
    CaseRagResult,
    CaseRagStatus,
    HistoricalCaseRead,
    SimilarCaseMatch,
)
from backend.app.schemas.common import AnalysisMode, ExecutionMode
from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


@dataclass
class RecordingExecutor:
    name: str
    delegate: object
    calls: list[str]
    inputs: list[object] = field(default_factory=list)
    error: Exception | None = None

    async def execute(self, stage_input):
        self.calls.append(self.name)
        self.inputs.append(stage_input)
        if self.error:
            raise self.error
        return await self.delegate.execute(stage_input)


def _local_executors(call_log: list[str], prefix: str = "local"):
    pricing = PricingService.from_file("backend/pricing_rules.json")
    return {
        "requirement": RecordingExecutor(
            f"{prefix}:requirement", LocalRequirementExecutor(), call_log
        ),
        "technical": RecordingExecutor(
            f"{prefix}:technical",
            LocalTechnicalExecutor(DurationService(pricing.rules)),
            call_log,
        ),
        "quote": RecordingExecutor(
            f"{prefix}:quote", LocalQuoteExecutor(pricing), call_log
        ),
        "reply": RecordingExecutor(
            f"{prefix}:reply", LocalReplyExecutor(), call_log
        ),
    }


class RecordingSearchService:
    def __init__(self, result: CaseRagResult, calls: list[str]):
        self.result = result
        self.calls = calls
        self.queries = []

    def search(self, query):
        self.calls.append("retrieval")
        self.queries.append(query)
        return self.result


def empty_search(calls: list[str]) -> RecordingSearchService:
    return RecordingSearchService(
        CaseRagResult(status=CaseRagStatus.EMPTY_LIBRARY), calls
    )


def matched_search(calls: list[str]) -> RecordingSearchService:
    stored = HistoricalCaseRead.model_validate(
        {
            "id": "case-id",
            "project_number": "CASE-QUIZ",
            "project_type": "web_app",
            "original_requirement": "在线刷题题库",
            "core_features": ["content_management"],
            "suggested_quote": {
                "min_amount": 1000,
                "max_amount": 2000,
                "currency": "CNY",
            },
            "final_deal_price": 1500,
            "estimated_duration": {
                "min_days": 5,
                "max_days": 10,
                "explanation": "估算",
            },
            "actual_duration_days": 12,
            "risks": [],
            "is_won": True,
            "lessons_learned": "提前确认题目格式",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
    )
    return RecordingSearchService(
        CaseRagResult(
            status=CaseRagStatus.MATCHED,
            matches=[
                SimilarCaseMatch(
                    case=stored.to_summary(),
                    similarity=0.8,
                    matched_signals=["project_type"],
                )
            ],
            candidate_count=1,
            highest_similarity=0.8,
        ),
        calls,
    )


@pytest.mark.asyncio
async def test_no_key_runs_five_steps_in_fixed_order(tmp_path) -> None:
    calls: list[str] = []
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        ),
        local_executors=_local_executors(calls),
        case_search_service=empty_search(calls),
    )

    result = await orchestrator.analyze("开发一个带后台管理的企业官网")

    assert calls == [
        "local:requirement",
        "retrieval",
        "local:technical",
        "local:quote",
        "local:reply",
    ]
    assert result.analysis_mode == AnalysisMode.LOCAL_FALLBACK
    assert result.fallback_occurred is False
    assert [step.step for step in result.telemetry.steps] == [
        "requirement",
        "case_retrieval",
        "technical",
        "quote",
        "reply",
    ]
    assert all(
        step.execution_mode == ExecutionMode.LOCAL_FALLBACK
        for step in result.telemetry.steps
        if step.step not in {"case_retrieval", "quote"}
    )
    assert result.telemetry.steps[1].execution_mode == ExecutionMode.LOCAL_RETRIEVAL
    assert result.telemetry.steps[3].execution_mode == ExecutionMode.LOCAL_RULES


@pytest.mark.asyncio
async def test_one_agent_failure_falls_back_only_that_stage(tmp_path) -> None:
    calls: list[str] = []
    local = _local_executors(calls, prefix="local")
    primary = _local_executors(calls, prefix="agent")
    primary["technical"].error = RuntimeError("provider unavailable")
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key="test-key",
            database_path=tmp_path / "data.sqlite3",
        ),
        primary_executors=primary,
        local_executors=local,
        case_search_service=empty_search(calls),
    )

    result = await orchestrator.analyze("开发一个商城，包含支付功能")

    assert calls == [
        "agent:requirement",
        "retrieval",
        "agent:technical",
        "local:technical",
        "local:quote",
        "agent:reply",
    ]
    assert result.analysis_mode == AnalysisMode.AGENTS
    assert result.fallback_occurred is True
    technical_step = result.telemetry.steps[2]
    assert technical_step.execution_mode == ExecutionMode.LOCAL_FALLBACK
    assert technical_step.fallback_used is True
    assert technical_step.error == "RuntimeError: provider unavailable"
    assert sum(step.fallback_used for step in result.telemetry.steps) == 1
    quote_step = result.telemetry.steps[3]
    assert quote_step.execution_mode == ExecutionMode.LOCAL_RULES
    assert quote_step.fallback_used is False


@pytest.mark.asyncio
async def test_pipeline_returns_one_unified_contract_without_key(tmp_path) -> None:
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        ),
        case_search_service=empty_search([]),
    )

    result = await orchestrator.analyze(
        "做一个带微信支付的小程序，预算5万，四周上线"
    )

    assert result.requirement.project_type == "mini_program"
    assert result.quote.pricing.currency == "CNY"
    assert result.client_reply
    assert result.telemetry.total_duration_ms >= 0


@pytest.mark.asyncio
async def test_pipeline_passes_matches_to_technical_and_quote_and_summarizes_impact(
    tmp_path,
) -> None:
    calls: list[str] = []
    local = _local_executors(calls)
    search = matched_search(calls)
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        ),
        local_executors=local,
        case_search_service=search,
    )

    result = await orchestrator.analyze("开发在线刷题题库")

    assert calls == [
        "local:requirement",
        "retrieval",
        "local:technical",
        "local:quote",
        "local:reply",
    ]
    assert search.queries[0].project_type == result.requirement.project_type
    assert search.queries[0].requirement_text == "开发在线刷题题库"
    assert local["technical"].inputs[0].similar_cases[0].case.project_number == "CASE-QUIZ"
    assert local["quote"].inputs[0].similar_cases == local["technical"].inputs[0].similar_cases
    assert result.case_rag.status == CaseRagStatus.MATCHED
    assert result.case_rag.used_by_agents == ["TechnicalAgent", "QuoteAgent"]
    assert result.case_rag.matches[0].impacts


@pytest.mark.asyncio
async def test_retrieval_failure_does_not_interrupt_pipeline_or_mark_agent_fallback(
    tmp_path,
) -> None:
    calls: list[str] = []
    service = RecordingSearchService(
        CaseRagResult(
            status=CaseRagStatus.FAILED,
            error="RuntimeError: historical case retrieval failed",
        ),
        calls,
    )
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        ),
        local_executors=_local_executors(calls),
        case_search_service=service,
    )

    result = await orchestrator.analyze("开发企业官网")

    assert result.case_rag.status == CaseRagStatus.FAILED
    assert result.fallback_occurred is False
    retrieval_step = result.telemetry.steps[1]
    assert retrieval_step.step == "case_retrieval"
    assert retrieval_step.error == result.case_rag.error
    assert result.client_reply
