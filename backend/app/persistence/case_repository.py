from __future__ import annotations

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from backend.app.persistence.database import connect
from backend.app.schemas.case import (
    CaseListQuery,
    HistoricalCaseCreate,
    HistoricalCaseListResponse,
    HistoricalCaseRead,
    HistoricalCaseUpdate,
)


class CaseRepositoryError(RuntimeError):
    pass


class CaseConflictError(CaseRepositoryError):
    pass


class CaseDataError(CaseRepositoryError):
    def __init__(self, case_id: str, field: str | None = None) -> None:
        self.case_id = case_id
        self.field = field
        detail = f"case {case_id} contains invalid persisted data"
        if field:
            detail += f" in {field}"
        super().__init__(detail)


@dataclass(frozen=True)
class CaseRetrievalCorpus:
    items: list[HistoricalCaseRead]
    warnings: list[str]


class CaseRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)

    def create(self, data: HistoricalCaseCreate) -> HistoricalCaseRead:
        now = datetime.now(timezone.utc)
        case = HistoricalCaseRead(
            id=str(uuid.uuid4()),
            created_at=now,
            updated_at=now,
            **data.model_dump(),
        )
        try:
            with connect(self.database_path) as connection:
                connection.execute(
                    """
                    INSERT INTO historical_cases (
                        id, project_number, project_type, original_requirement,
                        core_features_json, client_budget_json,
                        suggested_quote_json, final_deal_price,
                        estimated_duration_json, actual_duration_days,
                        risks_json, is_won, lessons_learned,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._case_values(case),
                )
        except sqlite3.IntegrityError as exc:
            raise CaseConflictError(
                f"project number already exists: {data.project_number}"
            ) from exc
        return case

    def get(self, case_id: str) -> HistoricalCaseRead | None:
        return self._get_by("id", case_id)

    def get_by_project_number(
        self, project_number: str
    ) -> HistoricalCaseRead | None:
        return self._get_by("project_number", project_number)

    def _get_by(self, column: str, value: str) -> HistoricalCaseRead | None:
        if column not in {"id", "project_number"}:
            raise ValueError("unsupported case lookup column")
        with connect(self.database_path) as connection:
            row = connection.execute(
                f"SELECT * FROM historical_cases WHERE {column} = ?", (value,)
            ).fetchone()
        if row is None:
            return None
        return self._row_to_case(row)

    def update(
        self, case_id: str, data: HistoricalCaseUpdate | HistoricalCaseCreate
    ) -> HistoricalCaseRead | None:
        current = self.get(case_id)
        if current is None:
            return None
        updated = HistoricalCaseRead(
            id=current.id,
            created_at=current.created_at,
            updated_at=datetime.now(timezone.utc),
            **data.model_dump(),
        )
        try:
            with connect(self.database_path) as connection:
                connection.execute(
                    """
                    UPDATE historical_cases SET
                        project_number = ?, project_type = ?,
                        original_requirement = ?, core_features_json = ?,
                        client_budget_json = ?, suggested_quote_json = ?,
                        final_deal_price = ?, estimated_duration_json = ?,
                        actual_duration_days = ?, risks_json = ?, is_won = ?,
                        lessons_learned = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (*self._mutable_values(updated), updated.updated_at.isoformat(), case_id),
                )
        except sqlite3.IntegrityError as exc:
            raise CaseConflictError(
                f"project number already exists: {data.project_number}"
            ) from exc
        return updated

    def delete(self, case_id: str) -> bool:
        with connect(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM historical_cases WHERE id = ?", (case_id,)
            )
        return cursor.rowcount > 0

    def count(self) -> int:
        with connect(self.database_path) as connection:
            return int(
                connection.execute(
                    "SELECT COUNT(*) FROM historical_cases"
                ).fetchone()[0]
            )

    def list(self, query: CaseListQuery) -> HistoricalCaseListResponse:
        where, parameters = self._filters(query)
        with connect(self.database_path) as connection:
            total = connection.execute(
                f"SELECT COUNT(*) FROM historical_cases{where}", parameters
            ).fetchone()[0]
            rows = connection.execute(
                f"""
                SELECT * FROM historical_cases{where}
                ORDER BY created_at DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, query.limit, query.offset),
            ).fetchall()
        items: list[HistoricalCaseRead] = []
        warnings: list[str] = []
        for row in rows:
            try:
                items.append(self._row_to_case(row))
            except CaseDataError:
                warnings.append(f"Skipped invalid case {row['id']}")
        return HistoricalCaseListResponse(
            items=items,
            total=total,
            limit=query.limit,
            offset=query.offset,
            warnings=warnings,
        )

    def list_for_retrieval(self) -> CaseRetrievalCorpus:
        with connect(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM historical_cases
                ORDER BY created_at DESC, rowid DESC
                LIMIT 2000
                """
            ).fetchall()
        items: list[HistoricalCaseRead] = []
        warnings: list[str] = []
        for row in rows:
            try:
                items.append(self._row_to_case(row))
            except CaseDataError:
                warnings.append(f"Skipped invalid case {row['id']}")
        return CaseRetrievalCorpus(items=items, warnings=warnings)

    @staticmethod
    def _filters(query: CaseListQuery) -> tuple[str, tuple[object, ...]]:
        clauses: list[str] = []
        parameters: list[object] = []
        if query.project_type:
            clauses.append("project_type = ?")
            parameters.append(query.project_type.strip().lower())
        if query.is_won is not None:
            clauses.append("is_won = ?")
            parameters.append(int(query.is_won))
        if query.q and query.q.strip():
            pattern = f"%{query.q.strip()}%"
            clauses.append(
                "(project_number LIKE ? OR original_requirement LIKE ? "
                "OR lessons_learned LIKE ?)"
            )
            parameters.extend((pattern, pattern, pattern))
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, tuple(parameters)

    @staticmethod
    def _case_values(case: HistoricalCaseRead) -> tuple[object, ...]:
        return (
            case.id,
            *CaseRepository._mutable_values(case),
            case.created_at.isoformat(),
            case.updated_at.isoformat(),
        )

    @staticmethod
    def _mutable_values(case: HistoricalCaseRead) -> tuple[object, ...]:
        return (
            case.project_number,
            case.project_type,
            case.original_requirement,
            json.dumps(case.core_features, ensure_ascii=False),
            case.client_budget.model_dump_json() if case.client_budget else None,
            case.suggested_quote.model_dump_json(),
            case.final_deal_price,
            case.estimated_duration.model_dump_json(),
            case.actual_duration_days,
            json.dumps(
                [risk.model_dump(mode="json") for risk in case.risks],
                ensure_ascii=False,
            ),
            int(case.is_won),
            case.lessons_learned,
        )

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> HistoricalCaseRead:
        case_id = str(row["id"])
        try:
            return HistoricalCaseRead.model_validate(
                {
                    "id": case_id,
                    "project_number": row["project_number"],
                    "project_type": row["project_type"],
                    "original_requirement": row["original_requirement"],
                    "core_features": json.loads(row["core_features_json"]),
                    "client_budget": (
                        json.loads(row["client_budget_json"])
                        if row["client_budget_json"]
                        else None
                    ),
                    "suggested_quote": json.loads(row["suggested_quote_json"]),
                    "final_deal_price": row["final_deal_price"],
                    "estimated_duration": json.loads(
                        row["estimated_duration_json"]
                    ),
                    "actual_duration_days": row["actual_duration_days"],
                    "risks": json.loads(row["risks_json"]),
                    "is_won": bool(row["is_won"]),
                    "lessons_learned": row["lessons_learned"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        except (json.JSONDecodeError, KeyError, TypeError, ValidationError) as exc:
            raise CaseDataError(case_id) from exc
