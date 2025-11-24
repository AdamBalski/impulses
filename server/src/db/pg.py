from __future__ import annotations

import json
import typing

import psycopg
from psycopg.rows import dict_row


class PgPool:
    def __init__(self, dsn: str):
        self._dsn = dsn

    def getconn(self) -> psycopg.Connection:
        return psycopg.connect(self._dsn, row_factory=dict_row)

    def execute(self, sql: str, params: typing.Sequence[typing.Any] | None = None) -> list[dict]:
        with self.getconn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                try:
                    rows = cur.fetchall()
                except psycopg.ProgrammingError:
                    rows = []
            conn.commit()
        return rows

def connect_from_json(conn_json: str) -> PgPool:
    cfg = json.loads(conn_json)
    parts = []
    for k in ("host", "port", "dbname", "user", "password", "sslmode"):
        v = cfg.get(k)
        if v is not None:
            parts.append(f"{k}={v}")
    dsn = " ".join(parts)
    return PgPool(dsn)
