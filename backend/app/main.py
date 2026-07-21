from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import analyses, cases, health
from backend.app.core.config import Settings
from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.persistence.case_repository import CaseRepository
from backend.app.persistence.migrations import MigrationRunner
from backend.app.pipeline.orchestrator import PipelineOrchestrator
from backend.app.retrieval.bm25_provider import LocalBm25CaseRetrievalProvider
from backend.app.retrieval.service import CaseSearchService


def create_app(
    settings: Settings | None = None,
    *,
    orchestrator: PipelineOrchestrator | None = None,
    repository: AnalysisRepository | None = None,
    migration_runner: MigrationRunner | None = None,
    case_search_service: CaseSearchService | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or AnalysisRepository(settings.database_path)
    database_capabilities = repository.initialize(migration_runner=migration_runner)
    case_repository = CaseRepository(settings.database_path)
    case_search_service = case_search_service or CaseSearchService(
        case_repository,
        LocalBm25CaseRetrievalProvider(),
    )
    orchestrator = orchestrator or PipelineOrchestrator(
        settings=settings,
        case_search_service=case_search_service,
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="外包客户需求分析、报价与回复助手",
    )
    app.state.settings = settings
    app.state.repository = repository
    app.state.case_repository = case_repository
    app.state.case_search_service = case_search_service
    app.state.orchestrator = orchestrator
    app.state.database_capabilities = database_capabilities
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(cases.router, prefix=settings.api_prefix)
    app.include_router(analyses.router, prefix=settings.api_prefix)
    return app
