from __future__ import annotations

import json
import time
import uuid
from typing import Any

import pydantic

from src.db.sqlite import SqlitePool


class AiChatSummary(pydantic.BaseModel):
    id: str
    user_id: str
    model_id: str
    model: str | None = None
    title: str
    created_at: int
    updated_at: int


class AiChatMessage(pydantic.BaseModel):
    id: str
    chat_id: str
    role: str
    content: str | None = None
    message_type: str = "text"
    model_id: str | None = None
    model: str | None = None
    request_started_at: int | None = None
    reasoning: dict[str, Any] | None = None
    display_charts: list[dict[str, Any]] | None = None
    payload: Any = None
    tool_call_id: str | None = None
    round: int | None = None
    created_at: int


class AiChat(pydantic.BaseModel):
    summary: AiChatSummary
    messages: list[AiChatMessage]


def _to_chat_summary(row: dict) -> AiChatSummary:
    return AiChatSummary(
        id=row.get("id"),
        user_id=row.get("user_id"),
        model_id=row.get("model_id"),
        model=row.get("model_name"),
        title=row.get("title") or "",
        created_at=int(row.get("created_at")),
        updated_at=int(row.get("updated_at")),
    )


def _to_chat_message(row: dict) -> AiChatMessage:
    payload_raw = row.get("payload_json")
    payload: Any = None
    if isinstance(payload_raw, str) and payload_raw.strip():
        payload = json.loads(payload_raw)
    return AiChatMessage(
        id=row.get("id"),
        chat_id=row.get("chat_id"),
        role=row.get("role") or "",
        content=row.get("content"),
        message_type=row.get("message_type") or "text",
        model_id=row.get("model_id"),
        model=row.get("model_name"),
        request_started_at=int(row.get("request_started_at")) if row.get("request_started_at") is not None else None,
        payload=payload,
        tool_call_id=row.get("tool_call_id"),
        round=int(row.get("round")) if row.get("round") is not None else None,
        created_at=int(row.get("created_at")),
    )


def _collapse_chat_messages(raw_messages: list[AiChatMessage]) -> list[AiChatMessage]:
    grouped_reasoning: dict[int, dict[str, Any]] = {}
    grouped_display_charts: dict[int, list[dict[str, Any]]] = {}
    visible_messages: list[AiChatMessage] = []

    def ensure_group(request_started_at: int) -> dict[str, Any]:
        group = grouped_reasoning.get(request_started_at)
        if group is None:
            group = {
                "notes": [],
                "tool_calls": [],
                "tool_calls_by_id": {},
            }
            grouped_reasoning[request_started_at] = group
        return group

    for message in raw_messages:
        request_started_at = message.request_started_at if message.request_started_at is not None else message.created_at

        if message.message_type == "reasoning_note":
            ensure_group(request_started_at)["notes"].append({
                "round": message.round if message.round is not None else 0,
                "content": message.content or "",
            })
            continue

        if message.message_type == "tool_call":
            group = ensure_group(request_started_at)
            tool_payload = message.payload if isinstance(message.payload, dict) else {}
            tool_trace = {
                "round": message.round if message.round is not None else 0,
                "tool_call_id": message.tool_call_id or message.id,
                "name": message.content or "(missing name)",
                "arguments": tool_payload.get("arguments"),
                "response": None,
            }
            group["tool_calls"].append(tool_trace)
            group["tool_calls_by_id"][tool_trace["tool_call_id"]] = tool_trace
            continue

        if message.message_type == "tool_response":
            group = ensure_group(request_started_at)
            payload = message.payload if isinstance(message.payload, dict) else {}
            tool_call_id = message.tool_call_id or message.id
            existing_trace = group["tool_calls_by_id"].get(tool_call_id)
            response = payload.get("response")
            if existing_trace is not None:
                existing_trace["response"] = response
            else:
                tool_trace = {
                    "round": message.round if message.round is not None else 0,
                    "tool_call_id": tool_call_id,
                    "name": "(missing name)",
                    "arguments": None,
                    "response": response,
                }
                group["tool_calls"].append(tool_trace)
                group["tool_calls_by_id"][tool_call_id] = tool_trace
            continue

        if message.message_type == "display_chart":
            request_display_charts = grouped_display_charts.get(request_started_at)
            if request_display_charts is None:
                request_display_charts = []
                grouped_display_charts[request_started_at] = request_display_charts
            request_display_charts.append({
                "round": message.round if message.round is not None else 0,
                "chart": message.payload if isinstance(message.payload, dict) else {},
            })
            continue

        visible_messages.append(message)

    collapsed_messages: list[AiChatMessage] = []
    for message in visible_messages:
        reasoning = None
        display_charts = None
        request_started_at = message.request_started_at if message.request_started_at is not None else message.created_at
        grouped = grouped_reasoning.get(request_started_at)
        grouped_display = grouped_display_charts.get(request_started_at)

        if message.role == "assistant" and grouped is not None:
            next_reasoning = {
                "notes": list(grouped["notes"]),
                "tool_calls": [
                    {
                        "round": tool_trace["round"],
                        "tool_call_id": tool_trace["tool_call_id"],
                        "name": tool_trace["name"],
                        "arguments": tool_trace["arguments"],
                        "response": tool_trace["response"],
                    }
                    for tool_trace in grouped["tool_calls"]
                ],
            }
            reasoning = next_reasoning

        if message.role == "assistant" and grouped_display:
            display_charts = list(grouped_display)

        collapsed_messages.append(message.model_copy(update={
            "reasoning": reasoning,
            "display_charts": display_charts,
        }))

    return collapsed_messages


class AiChatRepo:
    def __init__(self, pool: SqlitePool):
        self.pool = pool

    def list_chats(self, user_id: str) -> list[AiChatSummary]:
        rows = self.pool.execute(
            """
            select c.id,
                   c.user_id,
                   c.model_id,
                   m.model_name,
                   c.title,
                   c.created_at,
                   c.updated_at
            from ai_chat c
            left join llm_model m on m.id = c.model_id
            where c.user_id = ?
            order by c.updated_at desc, c.created_at desc, c.id asc
            """,
            [user_id],
        )
        return [_to_chat_summary(row) for row in rows]

    def get_chat_summary(self, user_id: str, chat_id: str) -> AiChatSummary | None:
        rows = self.pool.execute(
            """
            select c.id,
                   c.user_id,
                   c.model_id,
                   m.model_name,
                   c.title,
                   c.created_at,
                   c.updated_at
            from ai_chat c
            left join llm_model m on m.id = c.model_id
            where c.user_id = ? and c.id = ?
            """,
            [user_id, chat_id],
        )
        return _to_chat_summary(rows[0]) if rows else None

    def list_messages(self, chat_id: str) -> list[AiChatMessage]:
        rows = self.pool.execute(
            """
            select id,
                   chat_id,
                   role,
                   content,
                   message_type,
                   model_id,
                   model_name,
                   request_started_at,
                   payload_json,
                   tool_call_id,
                   round,
                   created_at
            from ai_chat_message
            where chat_id = ?
            order by created_at asc, rowid asc
            """,
            [chat_id],
        )
        return _collapse_chat_messages([_to_chat_message(row) for row in rows])

    def get_chat(self, user_id: str, chat_id: str) -> AiChat | None:
        summary = self.get_chat_summary(user_id, chat_id)
        if summary is None:
            return None
        return AiChat(
            summary=summary,
            messages=self.list_messages(chat_id),
        )

    def create_chat(self, user_id: str, model_id: str, title: str) -> AiChatSummary:
        now = int(time.time() * 1000)
        row = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "model_id": model_id,
            "title": title.strip(),
            "created_at": now,
            "updated_at": now,
        }
        self.pool.execute(
            """
            insert into ai_chat (id, user_id, model_id, title, created_at, updated_at)
            values (?, ?, ?, ?, ?, ?)
            """,
            [
                row["id"],
                row["user_id"],
                row["model_id"],
                row["title"],
                row["created_at"],
                row["updated_at"],
            ],
        )
        return self.get_chat_summary(user_id, row["id"])

    def update_chat_model(self, user_id: str, chat_id: str, model_id: str) -> AiChatSummary | None:
        self.pool.execute(
            """
            update ai_chat
            set model_id = ?,
                updated_at = ?
            where user_id = ? and id = ?
            """,
            [model_id, int(time.time() * 1000), user_id, chat_id],
        )
        return self.get_chat_summary(user_id, chat_id)

    def append_message(
        self,
        chat_id: str,
        role: str,
        content: str | None,
        model_id: str | None = None,
        model_name: str | None = None,
        message_type: str = "text",
        payload: Any = None,
        tool_call_id: str | None = None,
        round: int | None = None,
        *,
        request_started_at: int | None = None,
        created_at: int | None = None,
    ) -> AiChatMessage:
        now = created_at if created_at is not None else int(time.time() * 1000)
        request_started = request_started_at if request_started_at is not None else now
        row = {
            "id": str(uuid.uuid4()),
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "message_type": message_type,
            "model_id": model_id,
            "model_name": model_name,
            "request_started_at": request_started,
            "payload_json": json.dumps(payload, sort_keys=True) if payload is not None else None,
            "tool_call_id": tool_call_id,
            "round": round,
            "created_at": now,
        }
        self.pool.execute(
            """
            insert into ai_chat_message (
                id,
                chat_id,
                role,
                content,
                message_type,
                model_id,
                model_name,
                request_started_at,
                payload_json,
                tool_call_id,
                round,
                created_at
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                row["id"],
                row["chat_id"],
                row["role"],
                row["content"],
                row["message_type"],
                row["model_id"],
                row["model_name"],
                row["request_started_at"],
                row["payload_json"],
                row["tool_call_id"],
                row["round"],
                row["created_at"],
            ],
        )
        self.pool.execute(
            """
            update ai_chat
            set updated_at = ?
            where id = ?
            """,
            [now, chat_id],
        )
        return _to_chat_message(row)
