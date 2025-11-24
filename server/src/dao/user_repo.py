from __future__ import annotations

import typing

import pydantic

from src.db.pg import PgPool


class User(pydantic.BaseModel):
    id: str
    email: str
    role: str
    created_at: str | None = None
    password_hash: str | None = None  # present only in get_user_by_email

def _to_user(row: dict, include_password_hash: bool = False) -> User:
    data = {
        "id": row.get("id"),
        "email": row.get("email"),
        "role": row.get("role"),
        "created_at": row.get("created_at"),
    }
    if include_password_hash:
        data["password_hash"] = row.get("password_hash")
    return User(**data)

class UserRepo:
    def __init__(self, pool: PgPool):
        self.pool = pool

    def create_user(self, email: str, password_hash: str, role: str) -> User:
        rows = self.pool.execute(
            """
            insert into app_user (email, password_hash, role)
            values (%s, %s, %s)
            returning id::text as id, email, role::text as role, to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') as created_at
            """,
            [email, password_hash, role],
        )
        return _to_user(rows[0])

    def get_user_by_email(self, email: str) -> typing.Optional[User]:
        rows = self.pool.execute(
            """
            select id::text as id, email, role::text as role, to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') as created_at,
                   password_hash
            from app_user
            where email = %s and deleted_at is null
            """,
            [email],
        )
        return _to_user(rows[0], include_password_hash=True) if rows else None

    def get_user_by_id(self, user_id: str) -> typing.Optional[User]:
        rows = self.pool.execute(
            """
            select id::text as id, email, role::text as role, to_char(created_at, 'YYYY-MM-DD"T"HH24:MI:SSOF') as created_at
            from app_user
            where id = %s::uuid and deleted_at is null
            """,
            [user_id],
        )
        return _to_user(rows[0]) if rows else None

    def soft_delete_user(self, user_id: str) -> None:
        self.pool.execute(
            """
            update app_user set deleted_at = now() where id = %s::uuid and deleted_at is null
            """,
            [user_id],
        )
