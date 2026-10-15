from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

from backend.app.core.config import Settings
from backend.app.executors.agent_executor import AgentStageExecutor
from backend.app.executors.local.quote_executor import LocalQuoteExecutor
from backend.app.executors.local.reply_executor import LocalReplyExecutor
from backend.app.executors.local.requirement_executor import LocalRequirementExecutor
from backend.app.executors.local.technical_executor import LocalTechnicalExecutor
from backend.app.pipeline.telemetry import sanitize_error
from backend.app.persistence.case_repository import CaseRepository
from backend.app.retrieval.base import CaseSearchQuery
from backend.app.retrieval.bm25_provider import LocalBm25CaseRetrievalProvider
from backend.app.retrieval.insights import CaseInsightService
from backend.app.retrieval.service import CaseSearchService
from backend.app.schemas.analysis import AnalysisResponse, PipelineTelemetry, StepTelemetry
from backend.app.schemas.case import (
    CaseInsight,
    CaseRagResult,
    CaseRagStatus,
)
from backend.app.schemas.common import AnalysisMode, ExecutionMode, RiskCategory
from backend.app.schemas.quote import QuoteAgentInput, QuoteAgentOutput, QuoteResult
from backend.app.schemas.reply import ReplyAgentInput, ReplyAgentOutput
from backend.app.schemas.requirement import RequirementAgentInput, RequirementAgentOutput
from backend.app.schemas.technical import TechnicalAgentInput, TechnicalAgentOutput
from backend.app.services.duration_rules import DurationService
from backend.app.services.pricing import PricingService


logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        pricing_service: PricingService | None = None,
        primary_executors: dict[str, Any] | None = None,
        local_executors: dict[str, Any] | None = None,
        case_search_service: CaseSearchService | None = None,
        case_insight_service: CaseInsightService | None = None,
        clock: Callable[[], float] = time.perf_counter,
        id_factory: Callable[[], str] = lambda: str(uuid.uuid4()),
        now_factory: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.settings = settings
        self.clock = clock
        self.id_factory = id_factory
        self.now_factory = now_factory
        self.pricing_service = pricing_service or PricingService.from_file(
            settings.pricing_rules_path
        )
        self.case_search_service = case_search_service or CaseSearchService(
            CaseRepository(settings.database_path),
            LocalBm25CaseRetrievalProvider(),
        )
        self.case_insight_service = case_insight_service or CaseInsightService()
        self.local_executors = local_executors or self._build_local_executors()
        if settings.has_openai_key:
            self.primary_executors = primary_executors or self._build_agent_executors()
        else:
            self.primary_executors = {}

    def _build_local_executors(self) -> dict[str, Any]:
        duration_service = DurationService(self.pricing_service.rules)
        return {
            "requirement": LocalRequirementExecutor(),
            "technical": LocalTechnicalExecutor(duration_service),
            "quote": LocalQuoteExecutor(self.pricing_service),
            "reply": LocalReplyExecutor(),
        }

    def _build_agent_executors(self) -> dict[str, Any]:
        from agents import set_default_openai_api

        from backend.app.agents.reply_agent import build_reply_agent
        from backend.app.agents.requirement_agent import build_requirement_agent
        from backend.app.agents.technical_agent import build_technical_agent

        set_default_openai_api("chat_completions")
        model = self.settings.openai_model
        return {
            "requirement": AgentStageExecutor(
                agent=build_requirement_agent(model),
                output_type=RequirementAgentOutput,
            ),
            "technical": AgentStageExecutor(
                agent=build_technical_agent(model),
                output_type=TechnicalAgentOutput,
            ),
            "reply": AgentStageExecutor(
                agent=build_reply_agent(model),
                output_type=ReplyAgentOutput,
            ),
        }

    async def _run_stage(
        self,
        name: str,
        stage_input: BaseModel,
        output_type: type[BaseModel],
        analysis_mode: AnalysisMode,
        *,
        use_primary: bool = True,
    ) -> tuple[BaseModel, StepTelemetry]:
        started = self.clock()
        error: str | None = None
        fallback_used = False
        if not use_primary:
            raw_output = await self.local_executors[name].execute(stage_input)
            execution_mode = ExecutionMode.LOCAL_RULES
        elif analysis_mode == AnalysisMode.LOCAL_FALLBACK:
            raw_output = await self.local_executors[name].execute(stage_input)
            execution_mode = ExecutionMode.LOCAL_FALLBACK
        else:
            try:
                raw_output = await self.primary_executors[name].execute(stage_input)
                execution_mode = ExecutionMode.AGENT
            except Exception as exc:
                error = sanitize_error(exc)
                fallback_used = True
                execution_mode = ExecutionMode.LOCAL_FALLBACK
                logger.warning("Agent stage %s failed; using local fallback: %s", name, error)
                raw_output = await self.local_executors[name].execute(stage_input)

        if isinstance(raw_output, BaseModel):
            output = output_type.model_validate(raw_output.model_dump())
        else:
            output = output_type.model_validate(raw_output)
        elapsed_ms = max(0.0, (self.clock() - started) * 1000)
        return output, StepTelemetry(
            step=name,
            execution_mode=execution_mode,
            duration_ms=elapsed_ms,
            fallback_used=fallback_used,
            error=error,
        )

    def _retrieve_cases(
        self, requirement: RequirementAgentOutput, requirement_text: str
    ) -> tuple[CaseRagResult, CaseInsight, StepTelemetry]:
        started = self.clock()
        try:
            query = CaseSearchQuery(
                requirement_text=requirement_text,
                project_type=requirement.project_type,
                core_features=requirement.features,
                risk_categories=[
                    RiskCategory(value)
                    for value in requirement.risk_signals
                    if value in RiskCategory._value2member_map_
                ],
            )
            raw_result = self.case_search_service.search(query)
            result = CaseRagResult.model_validate(raw_result)
        except Exception as exc:
            result = CaseRagResult(
                status=CaseRagStatus.FAILED,
                error=sanitize_error(exc),
            )
        insight = self.case_insight_service.summarize(result.matches)
        elapsed_ms = max(0.0, (self.clock() - started) * 1000)
        metric = StepTelemetry(
            step="case_retrieval",
            execution_mode=ExecutionMode.LOCAL_RETRIEVAL,
            duration_ms=elapsed_ms,
            fallback_used=False,
            error=result.error if result.status == CaseRagStatus.FAILED else None,
            status=result.status.value,
            warning=result.warning,
        )
        return result, insight, metric

    @staticmethod
    def _attach_case_impacts(
        case_rag: CaseRagResult,
        technical: TechnicalAgentOutput,
        quote: QuoteAgentOutput,
    ) -> CaseRagResult:
        if case_rag.status != CaseRagStatus.MATCHED:
            return case_rag
        impacts = [*technical.case_impacts, *quote.case_impacts]
        updated_matches = []
        for match in case_rag.matches:
            matching_impacts = [
                impact
                for impact in impacts
                if impact.project_number == match.case.project_number
            ]
            used_by = [
                agent
                for agent in ("TechnicalAgent", "QuoteAgent")
                if any(impact.agent == agent for impact in matching_impacts)
            ]
            updated_matches.append(
                match.model_copy(
                    update={
                        "used_by_agents": used_by,
                        "impacts": matching_impacts,
                    }
                )
            )
        used_by_agents = [
            agent
            for agent in ("TechnicalAgent", "QuoteAgent")
            if any(impact.agent == agent for impact in impacts)
        ]
        return case_rag.model_copy(
            update={
                "matches": updated_matches,
                "used_by_agents": used_by_agents,
                "impact_summary": [impact.summary for impact in impacts],
            }
        )

    async def analyze(self, requirement_text: str) -> AnalysisResponse:
        started = self.clock()
        analysis_mode = (
            AnalysisMode.AGENTS
            if self.settings.has_openai_key
            else AnalysisMode.LOCAL_FALLBACK
        )
        telemetry_steps: list[StepTelemetry] = []

        requirement_input = RequirementAgentInput(requirement_text=requirement_text)
        requirement, metric = await self._run_stage(
            "requirement", requirement_input, RequirementAgentOutput, analysis_mode
        )
        telemetry_steps.append(metric)
        assert isinstance(requirement, RequirementAgentOutput)

        case_rag, case_insight, metric = self._retrieve_cases(
            requirement, requirement_input.requirement_text
        )
        telemetry_steps.append(metric)

        technical, metric = await self._run_stage(
            "technical",
            TechnicalAgentInput(
                requirement=requirement,
                similar_cases=case_rag.matches,
                case_insight=case_insight,
            ),
            TechnicalAgentOutput,
            analysis_mode,
        )
        telemetry_steps.append(metric)
        assert isinstance(technical, TechnicalAgentOutput)

        quote, metric = await self._run_stage(
            "quote",
            QuoteAgentInput(
                requirement=requirement,
                technical=technical,
                similar_cases=case_rag.matches,
                case_insight=case_insight,
            ),
            QuoteAgentOutput,
            analysis_mode,
            use_primary=False,
        )
        telemetry_steps.append(metric)
        assert isinstance(quote, QuoteAgentOutput)
        case_rag = self._attach_case_impacts(case_rag, technical, quote)

        reply, metric = await self._run_stage(
            "reply",
            ReplyAgentInput(
                requirement=requirement,
                technical=technical,
                quote=quote,
            ),
            ReplyAgentOutput,
            analysis_mode,
        )
        telemetry_steps.append(metric)
        assert isinstance(reply, ReplyAgentOutput)

        total_duration_ms = max(0.0, (self.clock() - started) * 1000)
        return AnalysisResponse(
            id=self.id_factory(),
            created_at=self.now_factory(),
            requirement_text=requirement_input.requirement_text,
            analysis_mode=analysis_mode,
            fallback_occurred=any(step.fallback_used for step in telemetry_steps),
            requirement=requirement,
            technical_solution=technical.solution,
            quote=QuoteResult.model_validate(quote.model_dump()),
            estimated_duration=technical.estimated_duration,
            risks=technical.risks,
            recommendation=technical.recommendation,
            follow_up_questions=reply.follow_up_questions,
            client_reply=reply.client_reply,
            telemetry=PipelineTelemetry(
                total_duration_ms=total_duration_ms,
                steps=telemetry_steps,
            ),
            case_rag=case_rag,
        )
