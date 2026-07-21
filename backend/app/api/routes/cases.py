from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse

from backend.app.api.dependencies import get_case_repository, get_case_search_service
from backend.app.persistence.case_repository import (
    CaseConflictError,
    CaseDataError,
    CaseRepository,
)
from backend.app.schemas.case import (
    CaseRagResult,
    CaseRagStatus,
    CaseSearchRequest,
    CaseListQuery,
    HistoricalCaseCreate,
    HistoricalCaseListResponse,
    HistoricalCaseRead,
    HistoricalCaseUpdate,
)
from backend.app.retrieval.base import CaseSearchQuery
from backend.app.retrieval.service import CaseSearchService


router = APIRouter(prefix="/cases", tags=["historical-cases"])


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "case_not_found", "message": "历史案例不存在"},
    )


def _data_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"code": "case_data_invalid", "message": "历史案例数据格式异常"},
    )


@router.post("", response_model=HistoricalCaseRead, status_code=status.HTTP_201_CREATED)
def create_case(
    payload: HistoricalCaseCreate,
    repository: Annotated[CaseRepository, Depends(get_case_repository)],
) -> HistoricalCaseRead:
    try:
        return repository.create(payload)
    except CaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "case_project_number_conflict",
                "message": "项目编号已存在",
            },
        ) from exc


@router.get("", response_model=HistoricalCaseListResponse)
def list_cases(
    repository: Annotated[CaseRepository, Depends(get_case_repository)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    project_type: str | None = None,
    is_won: bool | None = None,
    q: str | None = None,
) -> HistoricalCaseListResponse:
    return repository.list(
        CaseListQuery(
            limit=page_size,
            offset=(page - 1) * page_size,
            project_type=project_type,
            is_won=is_won,
            q=q,
        )
    )


@router.post("/search", response_model=CaseRagResult)
def search_cases(
    payload: CaseSearchRequest,
    service: Annotated[CaseSearchService, Depends(get_case_search_service)],
) -> CaseRagResult | Response:
    result = service.search(CaseSearchQuery.model_validate(payload.model_dump()))
    if result.status == CaseRagStatus.FAILED:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=result.model_dump(mode="json"),
        )
    return result


@router.get("/{case_id}", response_model=HistoricalCaseRead)
def get_case(
    case_id: str,
    repository: Annotated[CaseRepository, Depends(get_case_repository)],
) -> HistoricalCaseRead:
    try:
        case = repository.get(case_id)
    except CaseDataError as exc:
        raise _data_error() from exc
    if case is None:
        raise _not_found()
    return case


@router.put("/{case_id}", response_model=HistoricalCaseRead)
def update_case(
    case_id: str,
    payload: HistoricalCaseUpdate,
    repository: Annotated[CaseRepository, Depends(get_case_repository)],
) -> HistoricalCaseRead:
    try:
        case = repository.update(case_id, payload)
    except CaseConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "case_project_number_conflict",
                "message": "项目编号已存在",
            },
        ) from exc
    except CaseDataError as exc:
        raise _data_error() from exc
    if case is None:
        raise _not_found()
    return case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_case(
    case_id: str,
    repository: Annotated[CaseRepository, Depends(get_case_repository)],
) -> Response:
    if not repository.delete(case_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
