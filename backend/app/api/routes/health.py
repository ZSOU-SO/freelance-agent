from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict

from backend.app.api.dependencies import get_orchestrator
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.common import AnalysisMode


router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    service: str
    analysis_mode: AnalysisMode
    case_library: "CaseLibraryHealth"


class CaseLibraryHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str
    error: str | None = None


@router.get("/health", response_model=HealthResponse)
def health(
    request: Request,
    orchestrator: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
) -> HealthResponse:
    mode = (
        AnalysisMode.AGENTS
        if orchestrator.settings.has_openai_key
        else AnalysisMode.LOCAL_FALLBACK
    )
    available = request.app.state.database_capabilities.case_library_available
    case_status = "degraded"
    if available:
        case_status = (
            "ready" if request.app.state.case_repository.count() else "empty"
        )
    return HealthResponse(
        status="ok" if available else "degraded",
        service=orchestrator.settings.app_name,
        analysis_mode=mode,
        case_library=CaseLibraryHealth(
            status=case_status,
            error=None if available else "historical case library unavailable",
        ),
    )
