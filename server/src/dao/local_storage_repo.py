from __future__ import annotations

import typing

import pydantic

from src.db.pg import PgPool


class LocalStorageEntry(pydantic.BaseModel):
    id: str
    user_id: str
    key: str
    value: str
    created_at: int
    updated_at: int


def _to_entry(row: dict) -> LocalStorageEntry:
    return LocalStorageEntry(
        id=row.get("id"),
        user_id=row.get("user_id"),
        key=row.get("key"),
        value=row.get("value"),
        created_at=int(row.get("created_at")),
        updated_at=int(row.get("updated_at")),
    )


class LocalStorageRepo:
    def __init__(self, pool: PgPool):
        self.pool = pool

    def list_entries(self, user_id: str) -> list[LocalStorageEntry]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   key,
                   value,
                   extract(epoch from created_at)::bigint as created_at,
                   extract(epoch from updated_at)::bigint as updated_at
            from local_storage_entry
            where user_id = %s::uuid
            order by key asc
            """,
            [user_id],
        )
        return [_to_entry(r) for r in rows]

    def get_entry_by_key(self, user_id: str, key: str) -> typing.Optional[LocalStorageEntry]:
        rows = self.pool.execute(
            """
            select id::text as id,
                   user_id::text as user_id,
                   key,
                   value,
                   extract(epoch from created_at)::bigint as created_at,
                   extract(epoch from updated_at)::bigint as updated_at
            from local_storage_entry
            where user_id = %s::uuid and key = %s
            """,
            [user_id, key],
        )
        return _to_entry(rows[0]) if rows else None

    def upsert_entry(self, user_id: str, key: str, value: str) -> LocalStorageEntry:
        rows = self.pool.execute(
            """
            insert into local_storage_entry (user_id, key, value)
            values (%s::uuid, %s, %s)
            on conflict (user_id, key) do update
            set value = excluded.value,
                updated_at = now()
            returning id::text as id,
                      user_id::text as user_id,
                      key,
                      value,
                      extract(epoch from created_at)::bigint as created_at,
                      extract(epoch from updated_at)::bigint as updated_at
            """,
            [user_id, key, value],
        )
        return _to_entry(rows[0])

    def delete_entry(self, user_id: str, key: str) -> None:
        self.pool.execute(
            """
            delete from local_storage_entry where user_id = %s::uuid and key = %s
            """,
            [user_id, key],
        )

    def delete_entry_by_id(self, user_id: str, entry_id: str) -> None:
        self.pool.execute(
            """
            delete from local_storage_entry where user_id = %s::uuid and id = %s::uuid
            """,
            [user_id, entry_id],
        )
