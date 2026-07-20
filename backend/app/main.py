from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import analyses, health
from backend.app.core.config import Settings
from backend.app.persistence.analysis_repository import AnalysisRepository
from backend.app.pipeline.orchestrator import PipelineOrchestrator


def create_app(
    settings: Settings | None = None,
    *,
    orchestrator: PipelineOrchestrator | None = None,
    repository: AnalysisRepository | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    repository = repository or AnalysisRepository(settings.database_path)
    repository.initialize()
    orchestrator = orchestrator or PipelineOrchestrator(settings=settings)

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="外包客户需求分析、报价与回复助手",
    )
    app.state.settings = settings
    app.state.repository = repository
    app.state.orchestrator = orchestrator
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(analyses.router, prefix=settings.api_prefix)
    return app
