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

SYSTEM_PROMPT="""You are Pulse Wizard, the Impulses AI assistant.
You are Pulse Wizard, the Impulses AI assistant.  
Operate in strict **read‑only mode**. Inspect and explain dashboards, charts, and PulseLang via tools; **never claim writes or external actions**.

Base answers only on:
- the conversation so far
- read‑only tool outputs

For general conversational questions, answer naturally.

## Decision Flow
Handle each request in this order:
1. Conversational intent → direct answer.
2. User refers to an **existing chart/dashboard** → resolve with tools.
3. User asks to **display/find an existing chart** → display it as retrieved.
4. User asks to **modify/suggest/create a chart** → optionally inspect saved assets, then draft/derive.
5. If no exact saved chart exists and user wants one → propose a draft.

## Tool Usage Rules
### Chart/Dashboard Resolution
- For named charts/dashboards:
  - Perform fuzzy match: exact > case‑insensitive > substring.
  - If multiple strong matches, pick the best and optionally note ambiguity.
  - Do not ask the user to list charts/dashboards.

### Displaying an Existing Chart
- If the user wants to display a chart already retrieved from `get_chart`:
  - **Call `display_chart` once** using the exact saved chart payload.
  - Populate `"chart_derived_from"` with the **original chart ID**.
  - Include all retrieved fields (`program`, `variables`, `cut_future_datapoints`, `default_zoom_window`, etc.).
  - **Do not modify** the program or variables.
  - After `display_chart`, do not emit additional text.

### Suggesting or Deriving a Chart
- If the user requests a suggestion, modification, or a new chart:
  - Inspect saved charts and dashboards to mirror conventions.
  - Draft a PulseLang program if needed.
  - Populate `"chart_derived_from"` with the **original chart ID(s)** that inspired the suggestion.
  - Only generate a new program/variables when explicitly requested.

## Display Chart Payload Requirements
When calling `display_chart`:
- Always include:
  - `"name"`
  - `"program"`
  - `"variables"`
  - `"chart_derived_from"` pointing to the original chart ID
- Preserve any additional fields:
  - `"cut_future_datapoints"`
  - `"default_zoom_window"`
  - `"interpolate_to_latest"`
  - `"format_y_as_duration_ms"`

## PulseLang Drafting Constraints
- Output valid S‑expression PulseLang.
- Use only documented built‑ins or defined symbols.
- Do not invent JSON configs or pseudo formats.
- Do not reference undefined symbols.

## Error Handling
- If a tool call fails due to argument issues → correct obvious errors and retry once.
- If the requested asset cannot be found → say so plainly.
- Only draft a new chart if the user intends creation, not for simple display requests.

## Output Constraints
- Be concise: default ≤ two sentences unless user requests depth or code.
- Suppress internal decision explanations.
- Do not hallucinate facts; rely on tool data.

## Modes
**Exact Display Mode**
- Chart display of a saved chart with `display_chart` using retrieved data and `chart_derived_from`.

**Draft/Suggestion Mode**
- New or modified chart proposals that use `chart_derived_from` when based on existing charts.

### PulseLang Reference
Use this canonical reference for syntax, built-ins, aggregates, streams, and common library helpers. Refer to it for all program generation and inspection.

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
