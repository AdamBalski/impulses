from __future__ import annotations

import pathlib
import sqlite3
import typing


class DuplicateKeyError(Exception):
    pass


class SqlitePool:
    def __init__(self, db_path: str):
        self._db_path = db_path
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    def getconn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("pragma foreign_keys = on")
        return conn

    def execute(self, sql: str, params: typing.Sequence[typing.Any] | None = None) -> list[dict]:
        with self.getconn() as conn:
            cur = conn.execute(sql, params or [])
            rows = [dict(row) for row in cur.fetchall()] if cur.description else []
            conn.commit()
        return rows


def connect(db_path: str) -> SqlitePool:
    return SqlitePool(db_path)
