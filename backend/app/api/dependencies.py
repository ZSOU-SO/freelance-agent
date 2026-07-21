from fastapi import HTTPException, Request, status

from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.persistence.case_repository import CaseRepository
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.retrieval.service import CaseSearchService


def get_orchestrator(request: Request) -> PipelineOrchestrator:
    return request.app.state.orchestrator


def get_repository(request: Request) -> AnalysisRepository:
    return request.app.state.repository


def get_case_repository(request: Request) -> CaseRepository:
    if not request.app.state.database_capabilities.case_library_available:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "case_library_unavailable",
                "message": "历史案例库暂不可用",
            },
        )
    return request.app.state.case_repository


def get_case_search_service(request: Request) -> CaseSearchService:
    get_case_repository(request)
    return request.app.state.case_search_service
