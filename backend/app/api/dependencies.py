from fastapi import Request

from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.pipeline.orchestrator import PipelineOrchestrator


def get_orchestrator(request: Request) -> PipelineOrchestrator:
    return request.app.state.orchestrator


def get_repository(request: Request) -> AnalysisRepository:
    return request.app.state.repository

