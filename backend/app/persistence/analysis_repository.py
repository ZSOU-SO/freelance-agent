from __future__ import annotations

from pathlib import Path

from backend.app.persistence.database import connect, initialize_database
from backend.app.schemas.analysis import AnalysisListResponse, AnalysisResponse


class AnalysisRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self) -> None:
        initialize_database(self.database_path)

    def save(self, analysis: AnalysisResponse) -> None:
        with connect(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO analyses (
                    id, requirement_text, result_json, analysis_mode,
                    fallback_occurred, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis.id,
                    analysis.requirement_text,
                    analysis.model_dump_json(),
                    analysis.analysis_mode.value,
                    int(analysis.fallback_occurred),
                    analysis.created_at.isoformat(),
                ),
            )

    def get(self, analysis_id: str) -> AnalysisResponse | None:
        with connect(self.database_path) as connection:
            row = connection.execute(
                "SELECT result_json FROM analyses WHERE id = ?", (analysis_id,)
            ).fetchone()
        if row is None:
            return None
        return AnalysisResponse.model_validate_json(row["result_json"])

    def list(self, *, limit: int, offset: int) -> AnalysisListResponse:
        with connect(self.database_path) as connection:
            total = connection.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
            rows = connection.execute(
                """
                SELECT result_json
                FROM analyses
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return AnalysisListResponse(
            items=[
                AnalysisResponse.model_validate_json(row["result_json"])
                for row in rows
            ],
            total=total,
            limit=limit,
            offset=offset,
        )

