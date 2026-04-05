from __future__ import annotations

import time
import typing
import uuid

import pydantic

from src.db.sqlite import SqlitePool


class Token(pydantic.BaseModel):
    id: str
    user_id: str | None = None
    name: str
    capability: str
    expires_at: int
    created_at: int | None = None
    token_hash: str | None = None

def _to_token(row: dict) -> Token:
    return Token(
        id=row.get("id"),
        user_id=row.get("user_id"),
        name=row.get("name"),
        capability=row.get("capability"),
        expires_at=int(row.get("expires_at")),
        created_at=int(row.get("created_at")) if row.get("created_at") is not None else None,
        token_hash=row.get("token_hash"),
    )

class TokenRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_tokens(self, user_id: str) -> list[Token]:
        rows = self.pool.execute(
            """
            select id,
                   name,
                   capability,
                   expires_at,
                   created_at
            from data_token
            where user_id = ?
            order by created_at desc
            """,
            [user_id],
        )
        return [_to_token(r) for r in rows]

    def create_token(self, user_id: str, name: str, capability: str, expires_at_ts: int, token_hash: str) -> Token:
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "token_hash": token_hash,
            "capability": capability,
            "expires_at": expires_at_ts,
            "created_at": int(time.time()),
        }
        self.pool.execute(
            """
            insert into data_token (id, user_id, name, token_hash, capability, expires_at, created_at)
            values (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["id"],
                row["user_id"],
                row["name"],
                row["token_hash"],
                row["capability"],
                row["expires_at"],
                row["created_at"],
            ],
        )
        return _to_token(row)

    def delete_token_by_name(self, user_id: str, name: str) -> None:
        self.pool.execute(
            """
            delete from data_token where user_id = ? and name = ?
            """,
            [user_id, name],
        )

    def get_token_hash_and_capability(self, user_id: str, name: str) -> typing.Optional[dict]:
        rows = self.pool.execute(
            """
            select token_hash, capability
            from data_token
            where user_id = ? and name = ? and ? < expires_at
            """,
            [user_id, name, int(time.time())],
        )
        return rows[0] if rows else None

    def list_all_active_tokens(self) -> list[Token]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   token_hash,
                   capability,
                   expires_at,
                   created_at
            from data_token
            where ? < expires_at
            order by created_at desc
            """,
            [int(time.time())],
        )
        return [_to_token(r) for r in rows]
    
    def get_token_by_id(self, token_id: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   token_hash,
                   capability,
                   expires_at,
                   created_at
            from data_token
            where id = ?
            """,
            [token_id],
        )
        return _to_token(rows[0]) if rows else None
    
    def get_token_by_name(self, user_id: str, name: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   token_hash,
                   capability,
                   expires_at,
                   created_at
            from data_token
            where user_id = ? and name = ?
            """,
            [user_id, name],
        )
        return _to_token(rows[0]) if rows else None

    def delete_token_by_id(self, user_id: str, token_id: str) -> None:
        self.pool.execute(
            """
            delete from data_token where user_id = ? and id = ?
            """,
            [user_id, token_id],
        )

    def get_token_by_hash(self, user_id: str, token_hash: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   token_hash,
                   capability,
                   expires_at,
                   created_at
            from data_token
            where user_id = ? and token_hash = ?
            """,
            [user_id, token_hash],
        )
        return _to_token(rows[0]) if rows else None
