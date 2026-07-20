from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    openai_api_key: str | None = None
    openai_model: str | None = None
    database_path: Path = PROJECT_DIR / "backend" / "data" / "freelance_agent.sqlite3"
    pricing_rules_path: Path = BACKEND_DIR / "pricing_rules.json"
    frontend_origin: str = "http://localhost:5173"
    app_name: str = "freelance-agent"
    api_prefix: str = "/api/v1"
    agent_timeout_seconds: float = Field(default=90.0, gt=0)

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    @classmethod
    def from_env(cls) -> "Settings":
        key = os.getenv("OPENAI_API_KEY", "").strip() or None
        model = os.getenv("OPENAI_MODEL", "").strip() or None
        database_value = os.getenv("DATABASE_PATH", "").strip()
        pricing_value = os.getenv("PRICING_RULES_PATH", "").strip()
        return cls(
            openai_api_key=key,
            openai_model=model,
            database_path=(Path(database_value) if database_value else cls.model_fields["database_path"].default),
            pricing_rules_path=(Path(pricing_value) if pricing_value else cls.model_fields["pricing_rules_path"].default),
            frontend_origin=os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"),
        )

