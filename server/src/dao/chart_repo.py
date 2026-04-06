from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pydantic

from src.db.sqlite import SqlitePool


class Chart(pydantic.BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    program: str
    variables: list[dict[str, Any]]
    format_y_as_duration_ms: bool
    interpolate_to_latest: bool
    cut_future_datapoints: bool
    default_zoom_window: str | None = None
    created_at: int
    updated_at: int


def _to_chart(row: dict) -> Chart:
    return Chart(
        id=row.get("id"),
        user_id=row.get("user_id"),
        name=row.get("name") or "",
        description=row.get("description") or "",
        program=row.get("program") or "",
        variables=json.loads(row.get("variables_json") or "[]"),
        format_y_as_duration_ms=bool(row.get("format_y_as_duration_ms")),
        interpolate_to_latest=bool(row.get("interpolate_to_latest")),
        cut_future_datapoints=bool(row.get("cut_future_datapoints")),
        default_zoom_window=row.get("default_zoom_window"),
        created_at=int(row.get("created_at")),
        updated_at=int(row.get("updated_at")),
    )


class ChartRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_charts(self, user_id: str) -> list[Chart]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   description,
                   program,
                   variables_json,
                   format_y_as_duration_ms,
                   interpolate_to_latest,
                   cut_future_datapoints,
                   default_zoom_window,
                   created_at,
                   updated_at
            from chart
            where user_id = ?
            order by name asc, updated_at desc, id asc
            """,
            [user_id],
        )
        return [_to_chart(row) for row in rows]

    def get_chart_by_id(self, user_id: str, chart_id: str) -> Chart | None:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   description,
                   program,
                   variables_json,
                   format_y_as_duration_ms,
                   interpolate_to_latest,
                   cut_future_datapoints,
                   default_zoom_window,
                   created_at,
                   updated_at
            from chart
            where user_id = ? and id = ?
            """,
            [user_id, chart_id],
        )
        return _to_chart(rows[0]) if rows else None

    def create_chart(
        self,
        user_id: str,
        name: str,
        description: str,
        program: str,
        variables: list[dict[str, Any]],
        format_y_as_duration_ms: bool,
        interpolate_to_latest: bool,
        cut_future_datapoints: bool,
        default_zoom_window: str | None,
        created_at: int | None = None,
        updated_at: int | None = None,
    ) -> Chart:
        now = int(time.time())
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "description": description,
            "program": program,
            "variables_json": json.dumps(variables, sort_keys=True),
            "format_y_as_duration_ms": int(format_y_as_duration_ms),
            "interpolate_to_latest": int(interpolate_to_latest),
            "cut_future_datapoints": int(cut_future_datapoints),
            "default_zoom_window": default_zoom_window,
            "created_at": created_at if created_at is not None else now,
            "updated_at": updated_at if updated_at is not None else now,
        }
        self.pool.execute(
            """
            insert into chart (
                id,
                user_id,
                name,
                description,
                program,
                variables_json,
                format_y_as_duration_ms,
                interpolate_to_latest,
                cut_future_datapoints,
                default_zoom_window,
                created_at,
                updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["id"],
                row["user_id"],
                row["name"],
                row["description"],
                row["program"],
                row["variables_json"],
                row["format_y_as_duration_ms"],
                row["interpolate_to_latest"],
                row["cut_future_datapoints"],
                row["default_zoom_window"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        return _to_chart(row)

    def update_chart(
        self,
        user_id: str,
        chart_id: str,
        name: str,
        description: str,
        program: str,
        variables: list[dict[str, Any]],
        format_y_as_duration_ms: bool,
        interpolate_to_latest: bool,
        cut_future_datapoints: bool,
        default_zoom_window: str | None,
    ) -> Chart | None:
        self.pool.execute(
            """
            update chart
            set name = ?,
                description = ?,
                program = ?,
                variables_json = ?,
                format_y_as_duration_ms = ?,
                interpolate_to_latest = ?,
                cut_future_datapoints = ?,
                default_zoom_window = ?,
                updated_at = ?
            where user_id = ? and id = ?
            """,
            [
                name,
                description,
                program,
                json.dumps(variables, sort_keys=True),
                int(format_y_as_duration_ms),
                int(interpolate_to_latest),
                int(cut_future_datapoints),
                default_zoom_window,
                int(time.time()),
                user_id,
                chart_id,
            ],
        )
        return self.get_chart_by_id(user_id, chart_id)

    def delete_chart(self, user_id: str, chart_id: str) -> None:
        self.pool.execute(
            """
            delete from chart
            where user_id = ? and id = ?
            """,
            [user_id, chart_id],
        )
