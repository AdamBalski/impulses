from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pydantic

from src.db.sqlite import SqlitePool


class Dashboard(pydantic.BaseModel):
    id: str
    user_id: str
    name: str
    description: str
    program: str
    default_zoom_window: str | None = None
    override_chart_zoom: bool
    layout: list[dict[str, Any]]
    created_at: int
    updated_at: int


def _to_dashboard(row: dict) -> Dashboard:
    return Dashboard(
        id=row.get("id"),
        user_id=row.get("user_id"),
        name=row.get("name") or "",
        description=row.get("description") or "",
        program=row.get("program") or "",
        default_zoom_window=row.get("default_zoom_window"),
        override_chart_zoom=bool(row.get("override_chart_zoom")),
        layout=json.loads(row.get("layout_json") or "[]"),
        created_at=int(row.get("created_at")),
        updated_at=int(row.get("updated_at")),
    )


class DashboardRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_dashboards(self, user_id: str) -> list[Dashboard]:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   description,
                   program,
                   default_zoom_window,
                   override_chart_zoom,
                   layout_json,
                   created_at,
                   updated_at
            from dashboard
            where user_id = ?
            order by name asc, updated_at desc, id asc
            """,
            [user_id],
        )
        return [_to_dashboard(row) for row in rows]

    def get_dashboard_by_id(self, user_id: str, dashboard_id: str) -> Dashboard | None:
        rows = self.pool.execute(
            """
            select id,
                   user_id,
                   name,
                   description,
                   program,
                   default_zoom_window,
                   override_chart_zoom,
                   layout_json,
                   created_at,
                   updated_at
            from dashboard
            where user_id = ? and id = ?
            """,
            [user_id, dashboard_id],
        )
        return _to_dashboard(rows[0]) if rows else None

    def create_dashboard(
        self,
        user_id: str,
        name: str,
        description: str,
        program: str,
        default_zoom_window: str | None,
        override_chart_zoom: bool,
        layout: list[dict[str, Any]],
        created_at: int | None = None,
        updated_at: int | None = None,
    ) -> Dashboard:
        now = int(time.time())
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "name": name,
            "description": description,
            "program": program,
            "default_zoom_window": default_zoom_window,
            "override_chart_zoom": int(override_chart_zoom),
            "layout_json": json.dumps(layout, sort_keys=True),
            "created_at": created_at if created_at is not None else now,
            "updated_at": updated_at if updated_at is not None else now,
        }
        self.pool.execute(
            """
            insert into dashboard (
                id,
                user_id,
                name,
                description,
                program,
                default_zoom_window,
                override_chart_zoom,
                layout_json,
                created_at,
                updated_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["id"],
                row["user_id"],
                row["name"],
                row["description"],
                row["program"],
                row["default_zoom_window"],
                row["override_chart_zoom"],
                row["layout_json"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        return _to_dashboard(row)

    def update_dashboard(
        self,
        user_id: str,
        dashboard_id: str,
        name: str,
        description: str,
        program: str,
        default_zoom_window: str | None,
        override_chart_zoom: bool,
        layout: list[dict[str, Any]],
    ) -> Dashboard | None:
        self.pool.execute(
            """
            update dashboard
            set name = ?,
                description = ?,
                program = ?,
                default_zoom_window = ?,
                override_chart_zoom = ?,
                layout_json = ?,
                updated_at = ?
            where user_id = ? and id = ?
            """,
            [
                name,
                description,
                program,
                default_zoom_window,
                int(override_chart_zoom),
                json.dumps(layout, sort_keys=True),
                int(time.time()),
                user_id,
                dashboard_id,
            ],
        )
        return self.get_dashboard_by_id(user_id, dashboard_id)

    def delete_dashboard(self, user_id: str, dashboard_id: str) -> None:
        self.pool.execute(
            """
            delete from dashboard
            where user_id = ? and id = ?
            """,
            [user_id, dashboard_id],
        )
