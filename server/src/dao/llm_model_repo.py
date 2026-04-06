from __future__ import annotations

import json
import re
import time
import uuid
from urllib.parse import urlparse

import pydantic

from src.db.sqlite import SqlitePool


_HEADER_NAME_RE = r"^[A-Za-z0-9-]+$"
_LOCALHOST_HOSTS = {"localhost", "127.0.0.1", "::1"}


class LlmHeader(pydantic.BaseModel):
    name: str
    value: str

    @pydantic.field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Header name is required")
        if not re.fullmatch(_HEADER_NAME_RE, trimmed):
            raise ValueError("Header name contains invalid characters")
        return trimmed

    @pydantic.field_validator("value")
    @classmethod
    def validate_value(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Header value is required")
        return trimmed


class LlmModelSettings(pydantic.BaseModel):
    base_url: str
    headers: list[LlmHeader] = pydantic.Field(default_factory=list)
    is_localhost: bool = False

    @pydantic.field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        trimmed = value.strip().rstrip("/")
        if not trimmed:
            raise ValueError("Base URL is required")
        parsed = urlparse(trimmed)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Base URL must start with http:// or https://")
        if not parsed.netloc:
            raise ValueError("Base URL must include a host")
        return trimmed

    @pydantic.model_validator(mode="after")
    def validate_consistency(self) -> "LlmModelSettings":
        seen_headers: set[str] = set()
        for header in self.headers:
            key = header.name.lower()
            if key in seen_headers:
                raise ValueError("Header names must be unique")
            seen_headers.add(key)

        host = urlparse(self.base_url).hostname
        if self.is_localhost and host not in _LOCALHOST_HOSTS:
            raise ValueError("is_localhost=true requires a localhost base URL")
        return self


class LlmModel(pydantic.BaseModel):
    id: str
    user_id: str
    model_name: str
    settings: LlmModelSettings
    created_at: int
    updated_at: int


def _to_model(row: dict) -> LlmModel:
    return LlmModel(
        id=row.get("id"),
        user_id=row.get("user_id"),
        model_name=row.get("model_name") or "",
        settings=LlmModelSettings.model_validate(json.loads(row.get("settings_json"))),
        created_at=int(row.get("created_at")),
        updated_at=int(row.get("updated_at")),
    )


class LlmModelRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_models(self, user_id: str) -> list[LlmModel]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   model_name,
                   settings_json,
                   created_at,
                   updated_at
            from llm_model
            where user_id = ?
            order by updated_at desc, created_at desc, id asc
            """,
            [user_id],
        )
        return [_to_model(row) for row in rows]

    def get_model_by_id(self, user_id: str, model_id: str) -> LlmModel | None:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   model_name,
                   settings_json,
                   created_at,
                   updated_at
            from llm_model
            where user_id = ? and id = ?
            """,
            [user_id, model_id],
        )
        return _to_model(rows[0]) if rows else None

    def create_model(self, user_id: str, model_name: str, settings: LlmModelSettings) -> LlmModel:
        now = int(time.time())
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "model_name": model_name.strip(),
            # TODO: Replace plain persisted settings_json with envelope encryption before storing remote model secrets.
            "settings_json": json.dumps(settings.model_dump(mode="json"), sort_keys=True),
            "created_at": now,
            "updated_at": now,
        }
        self.pool.execute(
            """
            insert into llm_model (id, user_id, model_name, settings_json, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            [row["id"], row["user_id"], row["model_name"], row["settings_json"], row["created_at"], row["updated_at"]],
        )
        return _to_model(row)

    def update_model(self, user_id: str, model_id: str, model_name: str, settings: LlmModelSettings) -> LlmModel | None:
        now = int(time.time())
        self.pool.execute(
            """
            update llm_model
            set model_name = ?,
                settings_json = ?,
                updated_at = ?
            where user_id = ? and id = ?
            """,
            # TODO: Replace plain persisted settings_json with envelope encryption before updating remote model secrets.
            [model_name.strip(), json.dumps(settings.model_dump(mode="json"), sort_keys=True), now, user_id, model_id],
        )
        return self.get_model_by_id(user_id, model_id)

    def delete_model(self, user_id: str, model_id: str) -> None:
        self.pool.execute(
            """
            delete from llm_model
            where user_id = ? and id = ?
            """,
            [user_id, model_id],
        )
