from __future__ import annotations

import datetime
import sqlite3
import time
import typing
import uuid

import pydantic

from src.db.sqlite import DuplicateKeyError, SqlitePool


class User(pydantic.BaseModel):
    id: str
    email: str
    role: str
    created_at: str | None = None
    password_hash: str | None = None  # present only in get_user_by_email

def _epoch_to_iso(epoch: int | None) -> str | None:
    if epoch is None:
        return None
    return datetime.datetime.fromtimestamp(int(epoch), tz=datetime.timezone.utc).replace(microsecond=0).isoformat()

def _to_user(row: dict, include_password_hash: bool = False) -> User:
    data = {
        "id": row.get("id"),
        "email": row.get("email"),
        "role": row.get("role"),
        "created_at": _epoch_to_iso(row.get("created_at")),
    }
    if include_password_hash:
        data["password_hash"] = row.get("password_hash")
    return User(**data)

class UserRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def create_user(self, email: str, password_hash: str, role: str) -> User:
        row = {
            "id": str(uuid.uuid4()),
            "email": email,
            "password_hash": password_hash,
            "role": role,
            "created_at": int(time.time()),
        }
        try:
            self.pool.execute(
                """
                insert into app_user (id, email, password_hash, role, created_at)
                values (?, ?, ?, ?, ?)
                """,
                [row["id"], row["email"], row["password_hash"], row["role"], row["created_at"]],
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateKeyError(str(exc)) from exc
        return _to_user(row)

    def get_user_by_email(self, email: str) -> typing.Optional[User]:
        rows = self.pool.execute(
            """
            select id, email, role, created_at,
                   password_hash
            from app_user
            where email = ? and deleted_at is null
            """,
            [email],
        )
        return _to_user(rows[0], include_password_hash=True) if rows else None

    def get_user_by_id(self, user_id: str) -> typing.Optional[User]:
        rows = self.pool.execute(
            """
            select id, email, role, created_at
            from app_user
            where id = ? and deleted_at is null
            """,
            [user_id],
        )
        return _to_user(rows[0]) if rows else None

    def soft_delete_user(self, user_id: str) -> None:
        self.pool.execute(
            """
            update app_user set deleted_at = ? where id = ? and deleted_at is null
            """,
            [int(time.time()), user_id],
        )
