from __future__ import annotations

from dataclasses import dataclass

import pytest

from backend.app.core.config import Settings
from backend.app.executors.local.quote_executor import LocalQuoteExecutor
from backend.app.executors.local.reply_executor import LocalReplyExecutor
from backend.app.executors.local.requirement_executor import LocalRequirementExecutor
from backend.app.executors.local.technical_executor import LocalTechnicalExecutor
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.common import AnalysisMode, ExecutionMode
from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


@dataclass
class RecordingExecutor:
    name: str
    delegate: object
    calls: list[str]
    error: Exception | None = None

    async def execute(self, stage_input):
        self.calls.append(self.name)
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


@pytest.mark.asyncio
async def test_no_key_runs_four_local_steps_in_fixed_order(tmp_path) -> None:
    calls: list[str] = []
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        ),
        local_executors=_local_executors(calls),
    )

    result = await orchestrator.analyze("开发一个带后台管理的企业官网")

    assert calls == [
        "local:requirement",
        "local:technical",
        "local:quote",
        "local:reply",
    ]
    assert result.analysis_mode == AnalysisMode.LOCAL_FALLBACK
    assert result.fallback_occurred is False
    assert [step.step for step in result.telemetry.steps] == [
        "requirement",
        "technical",
        "quote",
        "reply",
    ]
    assert all(
        step.execution_mode == ExecutionMode.LOCAL_FALLBACK
        for step in result.telemetry.steps
    )


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
    )

    result = await orchestrator.analyze("开发一个商城，包含支付功能")

    assert calls == [
        "agent:requirement",
        "agent:technical",
        "local:technical",
        "agent:quote",
        "agent:reply",
    ]
    assert result.analysis_mode == AnalysisMode.AGENTS
    assert result.fallback_occurred is True
    technical_step = result.telemetry.steps[1]
    assert technical_step.execution_mode == ExecutionMode.LOCAL_FALLBACK
    assert technical_step.fallback_used is True
    assert technical_step.error == "RuntimeError: provider unavailable"
    assert sum(step.fallback_used for step in result.telemetry.steps) == 1


@pytest.mark.asyncio
async def test_pipeline_returns_one_unified_contract_without_key(tmp_path) -> None:
    orchestrator = PipelineOrchestrator(
        settings=Settings(
            openai_api_key=None,
            database_path=tmp_path / "data.sqlite3",
        )
    )

    result = await orchestrator.analyze(
        "做一个带微信支付的小程序，预算5万，四周上线"
    )

    assert result.requirement.project_type == "mini_program"
    assert result.quote.pricing.currency == "CNY"
    assert result.client_reply
    assert result.telemetry.total_duration_ms >= 0
