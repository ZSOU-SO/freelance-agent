from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from backend.app.persistence.migrations import MigrationRunner
from backend.app.pipeline.telemetry import sanitize_error


@dataclass(frozen=True)
class DatabaseCapabilities:
    analyses_available: bool
    case_library_available: bool
    case_library_error: str | None = None


def connect(database_path: str | Path) -> sqlite3.Connection:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=10)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(
    database_path: str | Path,
    *,
    migration_runner: MigrationRunner | None = None,
) -> DatabaseCapabilities:
    with connect(database_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id TEXT PRIMARY KEY,
                requirement_text TEXT NOT NULL,
                result_json TEXT NOT NULL,
                analysis_mode TEXT NOT NULL,
                fallback_occurred INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_analyses_created_at "
            "ON analyses(created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        connection.commit()
        try:
            (migration_runner or MigrationRunner()).apply(connection)
        except Exception as exc:
            return DatabaseCapabilities(
                analyses_available=True,
                case_library_available=False,
                case_library_error=sanitize_error(exc),
            )
    return DatabaseCapabilities(
        analyses_available=True,
        case_library_available=True,
    )
