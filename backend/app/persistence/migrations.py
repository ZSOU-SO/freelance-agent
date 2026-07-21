from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class Migration:
    version: str
    statements: tuple[str, ...]


@dataclass(frozen=True)
class MigrationReport:
    applied_versions: tuple[str, ...]


HISTORICAL_CASES_MIGRATION = Migration(
    version="20260721_01_historical_cases",
    statements=(
        """
        CREATE TABLE historical_cases (
            id TEXT PRIMARY KEY,
            project_number TEXT NOT NULL COLLATE NOCASE UNIQUE,
            project_type TEXT NOT NULL,
            original_requirement TEXT NOT NULL,
            core_features_json TEXT NOT NULL,
            client_budget_json TEXT,
            suggested_quote_json TEXT NOT NULL,
            final_deal_price INTEGER,
            estimated_duration_json TEXT NOT NULL,
            actual_duration_days INTEGER,
            risks_json TEXT NOT NULL,
            is_won INTEGER NOT NULL CHECK (is_won IN (0, 1)),
            lessons_learned TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            CHECK (final_deal_price IS NULL OR final_deal_price >= 0),
            CHECK (actual_duration_days IS NULL OR actual_duration_days > 0)
        )
        """,
        "CREATE INDEX idx_historical_cases_project_type ON historical_cases(project_type)",
        "CREATE INDEX idx_historical_cases_is_won ON historical_cases(is_won)",
        "CREATE INDEX idx_historical_cases_created_at ON historical_cases(created_at DESC)",
    ),
)


class MigrationRunner:
    def __init__(
        self, migrations: tuple[Migration, ...] = (HISTORICAL_CASES_MIGRATION,)
    ) -> None:
        self.migrations = migrations

    def apply(self, connection: sqlite3.Connection) -> MigrationReport:
        applied: list[str] = []
        for migration in self.migrations:
            existing = connection.execute(
                "SELECT 1 FROM schema_migrations WHERE version = ?",
                (migration.version,),
            ).fetchone()
            if existing is not None:
                continue
            try:
                connection.execute("BEGIN")
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                    (migration.version, datetime.now(timezone.utc).isoformat()),
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            applied.append(migration.version)
        return MigrationReport(applied_versions=tuple(applied))

