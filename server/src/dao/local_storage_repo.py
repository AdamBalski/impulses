from __future__ import annotations

import time
import typing
import uuid

import pydantic

from src.db.sqlite import SqlitePool


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
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_entries(self, user_id: str) -> list[LocalStorageEntry]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   key,
                   value,
                   created_at,
                   updated_at
            from local_storage_entry
            where user_id = ?
            order by key asc
            """,
            [user_id],
        )
        return [_to_entry(r) for r in rows]

    def get_entry_by_key(self, user_id: str, key: str) -> typing.Optional[LocalStorageEntry]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   key,
                   value,
                   created_at,
                   updated_at
            from local_storage_entry
            where user_id = ? and key = ?
            """,
            [user_id, key],
        )
        return _to_entry(rows[0]) if rows else None

    def upsert_entry(self, user_id: str, key: str, value: str) -> LocalStorageEntry:
        now = int(time.time())
        self.pool.execute(
            """
            insert into local_storage_entry (id, user_id, key, value, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?)
            on conflict (user_id, key) do update
            set value = excluded.value,
                updated_at = excluded.updated_at
            """,
            [str(uuid.uuid4()), user_id, key, value, now, now],
        )
        return self.get_entry_by_key(user_id, key)

    def delete_entry(self, user_id: str, key: str) -> None:
        self.pool.execute(
            """
            delete from local_storage_entry where user_id = ? and key = ?
            """,
            [user_id, key],
        )

    def delete_entry_by_id(self, user_id: str, entry_id: str) -> None:
        self.pool.execute(
            """
            delete from local_storage_entry where user_id = ? and id = ?
            """,
            [user_id, entry_id],
        )
