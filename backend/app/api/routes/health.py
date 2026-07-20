from typing import Annotated

from fastapi import APIRouter, Depends
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


@router.get("/health", response_model=HealthResponse)
def health(
    orchestrator: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
) -> HealthResponse:
    mode = (
        AnalysisMode.AGENTS
        if orchestrator.settings.has_openai_key
        else AnalysisMode.LOCAL_FALLBACK
    )
    return HealthResponse(
        status="ok",
        service=orchestrator.settings.app_name,
        analysis_mode=mode,
    )

