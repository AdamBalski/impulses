import asyncio
import json
import pathlib
import time
from collections.abc import Awaitable, Callable
from typing import Any

import fastapi
import pydantic

from src.ai.client_session_registry import ClientSessionRegistry
from src.ai.model_client import LlmChatCompletionResult, execute_chat_completion_from_stored_model
from src.ai.tool_executor import TOOL_DEFINITIONS, execute_ai_tool
from src.auth import user_auth
from src.auth.session import SessionStore
from src.common import state
from src.dao.ai_chat_repo import AiChat, AiChatMessage, AiChatRepo, AiChatSummary
from src.dao.chart_repo import ChartRepo
from src.dao.dashboard_repo import DashboardRepo
from src.dao.data_dao import DataDao
from src.dao.llm_model_repo import LlmModelRepo
from src.dao.user_repo import UserRepo

router = fastapi.APIRouter()

_MAX_TOOL_ROUNDS = 8
_TITLE_MAX_LENGTH = 120
_WS_HEARTBEAT_INTERVAL_SECONDS = 15.0
_PULSELANG_DOCS_PATH = pathlib.Path(__file__).resolve().parents[3] / "docs" / "PulseLang.md"
_PULSELANG_DOCS = _PULSELANG_DOCS_PATH.read_text(encoding="utf-8").strip()

SYSTEM_PROMPT = """You are Pulse Wizard, the Impulses AI assistant.

You are operating in read-only mode. You may inspect and explain dashboards, charts, and PulseLang definitions available through tools, but you must not claim to have changed data, executed writes, or taken actions outside the provided context.

PulseLang is Impulses' DSL for manipulating time-series and metric data. Users write PulseLang programs to define derived series, filters, rolling windows, aggregations, bucketization, and other chart or dashboard computations.

A chart is a saved visualization definition for one computed series view. It typically has a name, an optional description, a PulseLang program, variable/display settings, and a few rendering options such as default zoom or interpolation flags.

A dashboard is a saved layout that arranges multiple charts together. It typically has a name, an optional description, an optional dashboard-level PulseLang program, dashboard zoom settings, and a layout describing which charts appear and how they are arranged.

Base your answer only on:
- the conversation so far
- the read-only tool outputs you receive

For normal conversational or meta questions like greetings, "who are you", "what can you do", or similar, answer directly and naturally as Pulse Wizard. Do not force the conversation into charts or dashboards when the user is not asking about them.

You have read-only tools available for saved charts, dashboards, and metrics. Use them silently when needed for accuracy, and do not invent tool outputs.

When the user refers to a chart by name, you must call list_charts, inspect the returned chart names yourself, choose the best match yourself, and then call get_chart if needed. Do not ask the user to list charts for you.

When the user refers to a dashboard by name, you must call list_dashboards, inspect the returned dashboard names yourself, choose the best match yourself, and then call get_dashboard if needed.

If the user asks you to create, draft, or suggest a chart or PulseLang program, first inspect relevant saved charts, dashboards, or metrics when useful so you can mirror existing conventions. If no exact saved chart exists, you may still draft a new PulseLang program when the user is clearly asking for one.

If the user wants to see a chart, you must find the relevant saved chart, retrieve it, and then call display_chart with the chart payload so the UI renders it. Do not merely describe the chart when the user asked to see it.

If the user asks you to make, fix, revise, correct, or show a chart, you must produce the chart via display_chart before giving any user-facing prose about the result.

When a turn needs display_chart, do not first say things like "here is the chart", "I updated it", "I corrected it", or "here is the revised chart". Call display_chart first, then optionally add a short follow-up sentence.

If you emit a normal assistant text reply before calling display_chart, the turn will end and the chart will not be shown. Avoid that failure mode.

Do not claim that you updated, revised, corrected, or produced a chart unless you already called display_chart for that chart in the same turn.

If you already retrieved a saved chart and then want to display it, reuse the retrieved program and variables exactly. Do not rewrite, simplify, paraphrase, or synthesize a replacement chart payload.

When calling display_chart for an exact saved chart, the program must match the saved program to the letter.

When altering or fixing an existing chart, set chart_derived_from to the source chart id and make the smallest possible change. Preserve all unrelated fields exactly, including whitespace, newlines, and formatting in the untouched parts of the PulseLang program.

When you draft PulseLang, it must look like real PulseLang S-expressions used by Impulses. Do not output unrelated JSON configs, pseudo-tool calls, or made-up chart configuration formats.

If a requested saved chart or dashboard cannot be found, say so plainly. If the user wanted a new chart or program rather than an exact lookup, continue by proposing a draft instead of stopping at "not found".

If a tool call fails because your arguments or display payload were invalid, inspect the error and retry once with corrected arguments when the correction is obvious. Do not keep retrying repeatedly.

Do not mention tool names, function names, hidden context, or internal orchestration unless the user explicitly asks about them.

If the context is incomplete, say so plainly. When sharing code or config, use fenced code blocks with triple backticks.

Be really concise. Prefer short answers unless the user explicitly asks for depth.

Below is the canonical PulseLang reference. Use it as embedded documentation when reasoning about PulseLang syntax, runtime behavior, and examples.

--- BEGIN PULSELANG REFERENCE ---
""" + _PULSELANG_DOCS + """
--- END PULSELANG REFERENCE ---
"""

_DIRECT_REPLY_PATTERNS = (
    "who are you",
    "what are you",
    "what can you do",
    "how can you help",
    "help",
    "hello",
    "hi",
    "hey",
    "thanks",
    "thank you",
)


class ChatSendRequestBody(pydantic.BaseModel):
    content: str
    model_id: str | None = None
    chat_id: str | None = None


class ChatWebSocketSendBody(ChatSendRequestBody):
    type: str


class ToolTraceDto(pydantic.BaseModel):
    round: int
    tool_call_id: str
    name: str
    arguments: Any = None
    response: dict[str, Any]


class ReasoningNoteDto(pydantic.BaseModel):
    round: int
    content: str


class ChatReasoningDto(pydantic.BaseModel):
    notes: list[ReasoningNoteDto] = pydantic.Field(default_factory=list)
    tool_calls: list[ToolTraceDto] = pydantic.Field(default_factory=list)


class DisplayChartDto(pydantic.BaseModel):
    round: int
    chart: dict[str, Any]


class ChatMessageDto(pydantic.BaseModel):
    id: str
    role: str
    content: str | None = None
    model_id: str | None = None
    model: str | None = None
    request_started_at: int | None = None
    created_at: int
    reasoning: ChatReasoningDto | None = None
    display_charts: list[DisplayChartDto] = pydantic.Field(default_factory=list)


class ChatSummaryDto(pydantic.BaseModel):
    id: str
    model_id: str
    model: str | None = None
    title: str
    created_at: int
    updated_at: int


class ChatDto(pydantic.BaseModel):
    id: str
    model_id: str
    model: str | None = None
    title: str
    created_at: int
    updated_at: int
    messages: list[ChatMessageDto]


ProgressCallback = Callable[[dict[str, Any]], Awaitable[None]]
MessageSavedCallback = Callable[[AiChatMessage], Awaitable[None]]
ChatCreatedCallback = Callable[[AiChatSummary], Awaitable[None]]


def _assistant_message_from_result(result: LlmChatCompletionResult) -> dict[str, Any]:
    raw_message = result.raw_message or {}
    message: dict[str, Any] = {
        "role": "assistant",
        "content": raw_message.get("content") if raw_message.get("content") is not None else "",
    }
    tool_calls = raw_message.get("tool_calls")
    if isinstance(tool_calls, list) and tool_calls:
        message["tool_calls"] = tool_calls
    return message


def _final_assistant_content(result: LlmChatCompletionResult) -> str | None:
    reply = (result.reply or "").strip()
    if reply:
        return reply
    return None


def _tool_result_message(tool_call_id: str, payload: dict[str, Any]) -> dict[str, str]:
    return {
        "role": "tool",
        "tool_call_id": tool_call_id,
        "content": json.dumps(payload, ensure_ascii=True, sort_keys=True),
    }


def _normalize_user_message_content(content: str) -> str:
    trimmed = content.strip()
    if not trimmed:
        raise fastapi.HTTPException(status_code=422, detail="Chat message must have non-empty content")
    return trimmed


def _should_enable_tools(messages: list[dict[str, str]]) -> bool:
    last_user_message = next((message for message in reversed(messages) if message.get("role") == "user"), None)
    if not last_user_message:
        return True

    content = (last_user_message.get("content") or "").strip().lower()
    if not content:
        return True

    normalized = " ".join(content.split())
    return normalized not in _DIRECT_REPLY_PATTERNS


def _normalize_tool_arguments(arguments: Any) -> Any:
    if isinstance(arguments, str):
        trimmed = arguments.strip()
        if not trimmed:
            return {}
        try:
            return json.loads(trimmed)
        except json.JSONDecodeError:
            return trimmed
    return arguments


def _derive_chat_title(message: str) -> str:
    normalized = " ".join(message.split())
    if not normalized:
        return "New chat"
    if len(normalized) <= _TITLE_MAX_LENGTH:
        return normalized
    return normalized[: _TITLE_MAX_LENGTH - 1].rstrip() + "…"


def _to_chat_summary_dto(chat: AiChatSummary) -> ChatSummaryDto:
    return ChatSummaryDto(
        id=chat.id,
        model_id=chat.model_id,
        model=chat.model,
        title=chat.title,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
    )


def _to_chat_message_dto(message: AiChatMessage) -> ChatMessageDto:
    reasoning = None
    if isinstance(message.reasoning, dict):
        reasoning = ChatReasoningDto.model_validate(message.reasoning)
    return ChatMessageDto(
        id=message.id,
        role=message.role,
        content=message.content,
        model_id=message.model_id,
        model=message.model,
        request_started_at=message.request_started_at,
        created_at=message.created_at,
        reasoning=reasoning,
        display_charts=[
            DisplayChartDto.model_validate(display_chart)
            for display_chart in (message.display_charts or [])
        ],
    )


def _to_chat_dto(chat: AiChat) -> ChatDto:
    return ChatDto(
        id=chat.summary.id,
        model_id=chat.summary.model_id,
        model=chat.summary.model,
        title=chat.summary.title,
        created_at=chat.summary.created_at,
        updated_at=chat.summary.updated_at,
        messages=[_to_chat_message_dto(message) for message in chat.messages],
    )


def _load_persisted_conversation(chat: AiChat | None) -> list[dict[str, str]]:
    if chat is None:
        return []
    conversation: list[dict[str, str]] = []
    for message in chat.messages:
        if message.role not in ("user", "assistant"):
            continue
        if not isinstance(message.content, str):
            continue
        if message.role == "assistant" and not message.content.strip():
            continue
        conversation.append({
            "role": message.role,
            "content": message.content,
        })
    return conversation


async def _authenticate_chat_websocket(
    websocket: fastapi.WebSocket,
    sessions: SessionStore,
    users: UserRepo,
) -> tuple[str, str]:
    session_token = websocket.cookies.get("sid")
    if not session_token:
        await websocket.close(code=4401, reason="No session")
        raise RuntimeError("No session")

    session = sessions.get(session_token)
    if not session:
        await websocket.close(code=4401, reason="Invalid session")
        raise RuntimeError("Invalid session")

    user = users.get_user_by_id(session.user_id)
    if not user:
        await websocket.close(code=4404, reason="User not found")
        raise RuntimeError("User not found")

    return session_token, user.id


async def _run_chat_completion(
    *,
    user_id: str,
    chat_id: str,
    model_id: str,
    conversation_messages: list[dict[str, str]],
    data_dao: DataDao,
    chart_repo: ChartRepo,
    dashboard_repo: DashboardRepo,
    model_repo: LlmModelRepo,
    client_session_registry: ClientSessionRegistry,
    persist_aux_message: MessageSavedCallback | None = None,
    on_progress: ProgressCallback | None = None,
) -> LlmChatCompletionResult:
    upstream_messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        *conversation_messages,
    ]
    tools_enabled = _should_enable_tools(conversation_messages)

    for round_index in range(_MAX_TOOL_ROUNDS):
        round_number = round_index + 1
        extra_body: dict[str, Any] | None = None
        if tools_enabled:
            extra_body = {
                "tools": TOOL_DEFINITIONS,
                "tool_choice": "auto",
            }

        _, result = await execute_chat_completion_from_stored_model(
            model_repo,
            user_id,
            model_id,
            upstream_messages,
            extra_body=extra_body,
            registry=client_session_registry,
        )

        raw_message = result.raw_message or {}
        tool_calls = raw_message.get("tool_calls")
        assistant_note = (result.reply or "").strip()
        upstream_messages.append(_assistant_message_from_result(result))

        if assistant_note and isinstance(tool_calls, list) and tool_calls:
            note_payload = {
                "message_type": "reasoning_note",
                "round": round_number,
                "content": assistant_note,
            }
            if persist_aux_message is not None:
                await persist_aux_message(note_payload)
            if on_progress is not None:
                await on_progress({
                    "type": "chat_assistant_note",
                    "chat_id": chat_id,
                    "note": {
                        "round": round_number,
                        "content": assistant_note,
                    },
                })

        if not isinstance(tool_calls, list) or not tool_calls:
            return result

        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            tool_call_id = tool_call.get("id")
            function = tool_call.get("function")
            if not isinstance(tool_call_id, str) or not tool_call_id.strip():
                continue

            arguments = None
            tool_name = "(missing function)"
            if isinstance(function, dict):
                tool_name = function.get("name") if isinstance(function.get("name"), str) and function.get("name").strip() else "(missing name)"
                arguments = _normalize_tool_arguments(function.get("arguments"))

            if not isinstance(function, dict):
                payload = {
                    "ok": False,
                    "error": "Tool call payload was missing function data",
                }
            elif not isinstance(function.get("name"), str) or not function.get("name").strip():
                payload = {
                    "ok": False,
                    "error": "Tool call payload was missing function name",
                }
            else:
                try:
                    tool_data = execute_ai_tool(
                        user_id=user_id,
                        tool_name=function["name"],
                        arguments=function.get("arguments"),
                        data_dao=data_dao,
                        chart_repo=chart_repo,
                        dashboard_repo=dashboard_repo,
                    )
                    payload = {
                        "ok": True,
                        "data": tool_data,
                    }
                except fastapi.HTTPException as exc:
                    detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
                    payload = {
                        "ok": False,
                        "error": detail,
                    }
                except pydantic.ValidationError as exc:
                    payload = {
                        "ok": False,
                        "error": f"Invalid tool arguments: {exc}",
                    }
                except Exception as exc:
                    payload = {
                        "ok": False,
                        "error": f"Tool execution failed: {exc}",
                    }

            upstream_messages.append(_tool_result_message(tool_call_id, payload))
            if tool_name == "display_chart" and isinstance(arguments, dict) and payload.get("ok"):
                display_chart_payload = {
                    "message_type": "display_chart",
                    "round": round_number,
                    "payload": arguments,
                }
                if persist_aux_message is not None:
                    await persist_aux_message(display_chart_payload)
                if on_progress is not None:
                    await on_progress({
                        "type": "chat_display_chart",
                        "chat_id": chat_id,
                        "display_chart": {
                            "round": round_number,
                            "chart": arguments,
                        },
                    })
                continue

            tool_call_trace = {
                "round": round_number,
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "arguments": arguments,
                "response": payload,
            }
            if persist_aux_message is not None:
                await persist_aux_message({
                    "message_type": "tool_call",
                    "round": round_number,
                    "tool_call_id": tool_call_id,
                    "content": tool_name,
                    "payload": {
                        "arguments": arguments,
                    },
                })
                await persist_aux_message({
                    "message_type": "tool_response",
                    "round": round_number,
                    "tool_call_id": tool_call_id,
                    "content": "",
                    "payload": {
                        "response": payload,
                    },
                })
            if on_progress is not None:
                await on_progress({
                    "type": "chat_tool",
                    "chat_id": chat_id,
                    "tool_call": tool_call_trace,
                })

    raise fastapi.HTTPException(status_code=502, detail="LLM exceeded maximum tool-call iterations")


def _resolve_chat_model_id(body_model_id: str | None, persisted_chat: AiChat | None) -> str:
    requested_model_id = (body_model_id or "").strip()
    if requested_model_id:
        return requested_model_id
    if persisted_chat is not None and persisted_chat.summary.model_id:
        return persisted_chat.summary.model_id
    raise fastapi.HTTPException(status_code=422, detail="Saved model is required")


def _create_or_update_chat(
    *,
    chat_repo: AiChatRepo,
    user_id: str,
    persisted_chat: AiChat | None,
    model_id: str,
    first_user_message: str,
) -> AiChatSummary:
    if persisted_chat is None:
        created = chat_repo.create_chat(user_id, model_id, _derive_chat_title(first_user_message))
        if created is None:
            raise fastapi.HTTPException(status_code=500, detail="Failed to create chat")
        return created

    updated = chat_repo.update_chat_model(user_id, persisted_chat.summary.id, model_id)
    if updated is None:
        raise fastapi.HTTPException(status_code=404, detail="Chat not found")
    return updated


async def _handle_chat_turn(
    *,
    user_id: str,
    body: ChatSendRequestBody,
    data_dao: DataDao,
    chart_repo: ChartRepo,
    dashboard_repo: DashboardRepo,
    model_repo: LlmModelRepo,
    chat_repo: AiChatRepo,
    client_session_registry: ClientSessionRegistry,
    on_chat_created: ChatCreatedCallback | None = None,
    on_message_saved: MessageSavedCallback | None = None,
    on_progress: ProgressCallback | None = None,
) -> str:
    user_content = _normalize_user_message_content(body.content)
    chat_id = (body.chat_id or "").strip() or None
    persisted_chat = None if chat_id is None else chat_repo.get_chat(user_id, chat_id)
    if chat_id is not None and persisted_chat is None:
        raise fastapi.HTTPException(status_code=404, detail="Chat not found")

    model_id = _resolve_chat_model_id(body.model_id, persisted_chat)
    is_new_chat = persisted_chat is None
    chat_summary = _create_or_update_chat(
        chat_repo=chat_repo,
        user_id=user_id,
        persisted_chat=persisted_chat,
        model_id=model_id,
        first_user_message=user_content,
    )
    if is_new_chat and on_chat_created is not None:
        await on_chat_created(chat_summary)

    user_message_created_at = int(time.time() * 1000)
    user_message = chat_repo.append_message(
        chat_summary.id,
        "user",
        user_content,
        model_id=chat_summary.model_id,
        model_name=chat_summary.model,
        request_started_at=user_message_created_at,
        created_at=user_message_created_at,
    )
    if on_message_saved is not None:
        await on_message_saved(user_message)

    last_created_at = user_message_created_at
    saved_aux_message_count = 0

    async def persist_auxiliary_message(auxiliary_message: dict[str, Any]) -> None:
        nonlocal last_created_at, saved_aux_message_count
        last_created_at = max(int(time.time() * 1000), last_created_at + 1)
        saved_aux_message_count += 1
        saved = chat_repo.append_message(
            chat_summary.id,
            "assistant",
            auxiliary_message.get("content"),
            model_id=chat_summary.model_id,
            model_name=chat_summary.model,
            message_type=auxiliary_message["message_type"],
            payload=auxiliary_message.get("payload"),
            tool_call_id=auxiliary_message.get("tool_call_id"),
            round=auxiliary_message.get("round"),
            request_started_at=user_message_created_at,
            created_at=last_created_at,
        )
        if on_message_saved is not None and auxiliary_message["message_type"] in ("reasoning_note", "display_chart"):
            await on_message_saved(saved)

    conversation_messages = _load_persisted_conversation(chat_repo.get_chat(user_id, chat_summary.id))
    result = await _run_chat_completion(
        user_id=user_id,
        chat_id=chat_summary.id,
        model_id=model_id,
        conversation_messages=conversation_messages,
        data_dao=data_dao,
        chart_repo=chart_repo,
        dashboard_repo=dashboard_repo,
        model_repo=model_repo,
        client_session_registry=client_session_registry,
        persist_aux_message=persist_auxiliary_message,
        on_progress=on_progress,
    )

    final_content = _final_assistant_content(result)
    if final_content is not None:
        last_created_at = max(int(time.time() * 1000), last_created_at + 1)
        final_message = chat_repo.append_message(
            chat_summary.id,
            "assistant",
            final_content,
            model_id=chat_summary.model_id,
            model_name=chat_summary.model,
            request_started_at=user_message_created_at,
            created_at=last_created_at,
        )
        if on_message_saved is not None:
            await on_message_saved(final_message)
        return chat_summary.id

    if saved_aux_message_count > 0:
        last_created_at = max(int(time.time() * 1000), last_created_at + 1)
        chat_repo.append_message(
            chat_summary.id,
            "assistant",
            None,
            model_id=chat_summary.model_id,
            model_name=chat_summary.model,
            request_started_at=user_message_created_at,
            created_at=last_created_at,
        )
        return chat_summary.id

    saved_chat = chat_repo.get_chat(user_id, chat_summary.id)
    if saved_chat is None:
        raise fastapi.HTTPException(status_code=500, detail="Chat was saved but could not be reloaded")
    last_message = saved_chat.messages[-1] if saved_chat.messages else None
    if last_message is None or (
        last_message.role == "user"
        and (last_message.request_started_at or last_message.created_at) == user_message_created_at
    ):
        raise fastapi.HTTPException(status_code=502, detail="LLM returned an empty response")
    return chat_summary.id


@router.get("/chats", response_model=list[ChatSummaryDto])
def list_chats(
    chat_repo: AiChatRepo = state.injected(AiChatRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> list[ChatSummaryDto]:
    return [_to_chat_summary_dto(chat) for chat in chat_repo.list_chats(u.id)]


@router.get("/chats/{chat_id}", response_model=ChatDto)
def get_chat(
    chat_id: str,
    chat_repo: AiChatRepo = state.injected(AiChatRepo),
    u=fastapi.Depends(user_auth.get_current_user),
) -> ChatDto:
    chat = chat_repo.get_chat(u.id, chat_id)
    if chat is None:
        raise fastapi.HTTPException(status_code=404, detail="Chat not found")
    return _to_chat_dto(chat)
