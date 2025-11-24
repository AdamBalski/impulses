from __future__ import annotations

import typing

import pydantic

from src.db.pg import PgPool


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
    def __init__(self, pool: PgPool):
        self.pool = pool

    def list_tokens(self, user_id: str) -> list[Token]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   name,
                   capability::text as capability,
                   extract(epoch from expires_at)::bigint as expires_at,
                   extract(epoch from created_at)::bigint as created_at
            from data_token
            where user_id = %s::uuid
            order by created_at desc
            """,
            [user_id],
        )
        return [_to_token(r) for r in rows]

    def create_token(self, user_id: str, name: str, capability: str, expires_at_ts: int, token_hash: str) -> Token:
        rows = self.pool.execute(
            """
            insert into data_token (user_id, name, token_hash, capability, expires_at)
            values (%s::uuid, %s, %s, %s::token_capability, to_timestamp(%s))
            returning id::text as id,
                      name,
                      capability::text as capability,
                      extract(epoch from expires_at)::bigint as expires_at,
                      extract(epoch from created_at)::bigint as created_at
            """,
            [user_id, name, token_hash, capability, expires_at_ts],
        )
        return _to_token(rows[0])

    def delete_token_by_name(self, user_id: str, name: str) -> None:
        self.pool.execute(
            """
            delete from data_token where user_id = %s::uuid and name = %s
            """,
            [user_id, name],
        )

    def get_token_hash_and_capability(self, user_id: str, name: str) -> typing.Optional[dict]:
        rows = self.pool.execute(
            """
            select token_hash, capability::text as capability
            from data_token
            where user_id = %s::uuid and name = %s and now() < expires_at
            """,
            [user_id, name],
        )
        return rows[0] if rows else None

    def list_all_active_tokens(self) -> list[Token]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   name,
                   token_hash,
                   capability::text as capability,
                   extract(epoch from expires_at)::bigint as expires_at,
                   extract(epoch from created_at)::bigint as created_at
            from data_token
            where now() < expires_at
            order by created_at desc
            """,
            [],
        )
        return [_to_token(r) for r in rows]
    
    def get_token_by_id(self, token_id: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   name,
                   token_hash,
                   capability::text as capability,
                   extract(epoch from expires_at)::bigint as expires_at,
                   extract(epoch from created_at)::bigint as created_at
            from data_token
            where id = %s::uuid
            """,
            [token_id],
        )
        return _to_token(rows[0]) if rows else None
    
    def get_token_by_name(self, user_id: str, name: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   name,
                   token_hash,
                   capability::text as capability,
                   extract(epoch from expires_at)::bigint as expires_at,
                   extract(epoch from created_at)::bigint as created_at
            from data_token
            where user_id = %s::uuid and name = %s
            """,
            [user_id, name],
        )
        return _to_token(rows[0]) if rows else None

    def delete_token_by_id(self, user_id: str, token_id: str) -> None:
        self.pool.execute(
            """
            delete from data_token where user_id = %s::uuid and id = %s::uuid
            """,
            [user_id, token_id],
        )

    def get_token_by_hash(self, user_id: str, token_hash: str) -> typing.Optional[Token]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   name,
                   token_hash,
                   capability::text as capability,
                   extract(epoch from expires_at)::bigint as expires_at,
                   extract(epoch from created_at)::bigint as created_at
            from data_token
            where user_id = %s::uuid and token_hash = %s
            """,
            [user_id, token_hash],
        )
        return _to_token(rows[0]) if rows else None
