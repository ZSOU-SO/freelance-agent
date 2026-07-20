from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.app.api.dependencies import get_orchestrator, get_repository
from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.schemas.analysis import AnalysisListResponse, AnalysisRequest, AnalysisResponse


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyses", tags=["analyses"])


@router.post("", response_model=AnalysisResponse, status_code=status.HTTP_201_CREATED)
async def create_analysis(
    payload: AnalysisRequest,
    orchestrator: Annotated[PipelineOrchestrator, Depends(get_orchestrator)],
    repository: Annotated[AnalysisRepository, Depends(get_repository)],
) -> AnalysisResponse:
    try:
        result = await orchestrator.analyze(payload.requirement_text)
        repository.save(result)
        return result
    except Exception as exc:
        logger.exception("Analysis request failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="分析执行失败，请稍后重试",
        ) from exc


@router.get("", response_model=AnalysisListResponse)
def list_analyses(
    repository: Annotated[AnalysisRepository, Depends(get_repository)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> AnalysisListResponse:
    return repository.list(limit=limit, offset=offset)


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis(
    analysis_id: str,
    repository: Annotated[AnalysisRepository, Depends(get_repository)],
) -> AnalysisResponse:
    result = repository.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    return result

