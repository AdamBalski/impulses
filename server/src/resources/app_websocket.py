from __future__ import annotations

import asyncio

import fastapi
import pydantic

from src.ai.client_session_registry import ClientSessionRegistry
from src.common import state
from src.dao.ai_chat_repo import AiChatRepo
from src.dao.chart_repo import ChartRepo
from src.dao.dashboard_repo import DashboardRepo
from src.dao.data_dao import DataDao
from src.dao.llm_model_repo import LlmModelRepo
from src.dao.user_repo import UserRepo
from src.auth.session import SessionStore
from src.resources.ai import (
    ChatSendRequestBody,
    ChatWebSocketSendBody,
    _authenticate_chat_websocket,
    _handle_chat_turn,
    _to_chat_message_dto,
)

router = fastapi.APIRouter()

PING_INTERVAL_SECONDS = 4.0
PONG_TIMEOUT_SECONDS = 4.0


@router.websocket("/app")
async def app_socket(
    websocket: fastapi.WebSocket,
    app_state: state.AppState = fastapi.Depends(state.get_state),
) -> None:
    sessions = app_state.get_obj(SessionStore)
    users = app_state.get_obj(UserRepo)
    data_dao = app_state.get_obj(DataDao)
    chart_repo = app_state.get_obj(ChartRepo)
    dashboard_repo = app_state.get_obj(DashboardRepo)
    model_repo = app_state.get_obj(LlmModelRepo)
    chat_repo = app_state.get_obj(AiChatRepo)
    registry = app_state.get_obj(ClientSessionRegistry)

    try:
        session_token, user_id = await _authenticate_chat_websocket(websocket, sessions, users)
    except RuntimeError:
        return

    await websocket.accept()
    connection = await registry.register(user_id, session_token, websocket)
    pong_event = asyncio.Event()
    active_tasks: set[asyncio.Task[None]] = set()

    async def heartbeat_loop() -> None:
        while True:
            sent = await registry.send_to_connection(connection.connection_id, {"type": "ping"})
            if not sent:
                return
            pong_event.clear()
            try:
                await asyncio.wait_for(pong_event.wait(), timeout=PONG_TIMEOUT_SECONDS)
            except asyncio.TimeoutError:
                await registry.unregister(user_id, connection.connection_id)
                try:
                    await websocket.close(code=4408, reason="Heartbeat timeout")
                except Exception:
                    pass
                return
            await asyncio.sleep(PING_INTERVAL_SECONDS)

    async def process_chat_send(body: ChatWebSocketSendBody) -> None:
        created_chat_id: str | None = None
        source_connection_id = connection.connection_id

        async def on_chat_created(chat_summary) -> None:
            nonlocal created_chat_id
            created_chat_id = chat_summary.id
            await registry.send_to_connection(source_connection_id, {
                "type": "chat_id_assigned",
                "chat_id": chat_summary.id,
            })

        async def on_message_saved(message) -> None:
            if message.message_type != "text":
                return
            if message.role == "assistant" and not isinstance(message.content, str):
                return
            await registry.broadcast_to_user(user_id, {
                "type": "chat_message",
                "chat_id": message.chat_id,
                "message": _to_chat_message_dto(message).model_dump(mode="json"),
                "source_connection_id": source_connection_id,
            })

        async def on_progress(event: dict) -> None:
            await registry.broadcast_to_user(user_id, {
                **event,
                "source_connection_id": source_connection_id,
            })

        try:
            resolved_chat_id = await _handle_chat_turn(
                user_id=user_id,
                body=ChatSendRequestBody(
                    content=body.content,
                    model_id=body.model_id,
                    chat_id=body.chat_id,
                ),
                data_dao=data_dao,
                chart_repo=chart_repo,
                dashboard_repo=dashboard_repo,
                model_repo=model_repo,
                chat_repo=chat_repo,
                client_session_registry=registry,
                on_chat_created=on_chat_created,
                on_message_saved=on_message_saved,
                on_progress=on_progress,
            )
            await registry.broadcast_to_user(user_id, {
                "type": "chat_done",
                "chat_id": resolved_chat_id,
                "source_connection_id": source_connection_id,
            })
        except fastapi.HTTPException as exc:
            detail = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
            await registry.send_to_connection(source_connection_id, {
                "type": "chat_error",
                "chat_id": (body.chat_id or "").strip() or created_chat_id,
                "error": detail,
            })
        except pydantic.ValidationError as exc:
            await registry.send_to_connection(source_connection_id, {
                "type": "chat_error",
                "chat_id": (body.chat_id or "").strip() or created_chat_id,
                "error": str(exc),
            })
        except Exception as exc:
            await registry.send_to_connection(source_connection_id, {
                "type": "chat_error",
                "chat_id": (body.chat_id or "").strip() or created_chat_id,
                "error": f"Chat websocket failed: {exc}",
            })

    heartbeat_task = asyncio.create_task(heartbeat_loop())

    try:
        await registry.send_to_connection(connection.connection_id, {
            "type": "connected",
            "connection_id": connection.connection_id,
        })
        while True:
            message = await websocket.receive_json()
            message_type = message.get("type")
            await registry.mark_seen(user_id, connection.connection_id)

            if message_type == "pong":
                pong_event.set()
                continue

            if message_type == "ping":
                await registry.send_to_connection(connection.connection_id, {"type": "pong"})
                continue

            if message_type == "llm_response":
                request_id = message.get("request_id")
                if isinstance(request_id, str) and request_id:
                    await registry.resolve_request(request_id, message)
                continue

            if message_type == "chat_send":
                body = ChatWebSocketSendBody.model_validate(message)
                task = asyncio.create_task(process_chat_send(body))
                active_tasks.add(task)
                task.add_done_callback(active_tasks.discard)
                continue

            await registry.send_to_connection(connection.connection_id, {
                "type": "chat_error",
                "error": f"Unsupported websocket message type: {message_type or 'unknown'}",
            })
    except fastapi.WebSocketDisconnect:
        pass
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        for task in list(active_tasks):
            task.cancel()
        if active_tasks:
            await asyncio.gather(*active_tasks, return_exceptions=True)
        await registry.unregister(user_id, connection.connection_id)
