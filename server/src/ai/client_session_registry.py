from __future__ import annotations

import asyncio
import dataclasses
import time
import uuid
from typing import Any

import fastapi


@dataclasses.dataclass
class AppWebSocketConnection:
    connection_id: str
    user_id: str
    session_token: str
    websocket: fastapi.WebSocket
    last_seen_at: float
    outgoing_queue: asyncio.Queue[dict[str, Any]]
    sender_task: asyncio.Task[None]


@dataclasses.dataclass
class PendingClientRequest:
    request_id: str
    connection_id: str
    future: asyncio.Future[dict[str, Any]]


class ClientSessionRegistry:
    def __init__(self) -> None:
        self._connections_by_user: dict[str, list[AppWebSocketConnection]] = {}
        self._connections_by_id: dict[str, AppWebSocketConnection] = {}
        self._pending_requests: dict[str, PendingClientRequest] = {}
        self._lock = asyncio.Lock()

    async def register(self, user_id: str, session_token: str, websocket: fastapi.WebSocket) -> AppWebSocketConnection:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        connection = AppWebSocketConnection(
            connection_id=str(uuid.uuid4()),
            user_id=user_id,
            session_token=session_token,
            websocket=websocket,
            last_seen_at=time.time(),
            outgoing_queue=queue,
            sender_task=asyncio.create_task(self._sender_loop(user_id, queue, websocket)),
        )
        async with self._lock:
            current = self._connections_by_user.get(user_id, [])
            self._connections_by_user[user_id] = [*current, connection]
            self._connections_by_id[connection.connection_id] = connection
        return connection

    async def _sender_loop(
        self,
        user_id: str,
        queue: asyncio.Queue[dict[str, Any]],
        websocket: fastapi.WebSocket,
    ) -> None:
        try:
            while True:
                payload = await queue.get()
                await websocket.send_json(payload)
        except asyncio.CancelledError:
            raise
        except Exception:
            connection_id = await self._find_connection_id_by_socket(user_id, websocket)
            if connection_id is not None:
                await self.unregister(user_id, connection_id)

    async def _find_connection_id_by_socket(self, user_id: str, websocket: fastapi.WebSocket) -> str | None:
        async with self._lock:
            for connection in self._connections_by_user.get(user_id, []):
                if connection.websocket is websocket:
                    return connection.connection_id
        return None

    async def unregister(self, user_id: str, connection_id: str) -> None:
        connection_to_cancel: AppWebSocketConnection | None = None
        stale_requests: list[PendingClientRequest] = []

        async with self._lock:
            current = self._connections_by_user.get(user_id, [])
            remaining: list[AppWebSocketConnection] = []
            for connection in current:
                if connection.connection_id == connection_id:
                    connection_to_cancel = connection
                else:
                    remaining.append(connection)

            if remaining:
                self._connections_by_user[user_id] = remaining
            else:
                self._connections_by_user.pop(user_id, None)

            if connection_to_cancel is not None:
                self._connections_by_id.pop(connection_id, None)

            for request_id, pending in list(self._pending_requests.items()):
                if pending.connection_id == connection_id:
                    stale_requests.append(self._pending_requests.pop(request_id))

        for pending in stale_requests:
            if not pending.future.done():
                pending.future.set_exception(RuntimeError("Client websocket disconnected"))

        if connection_to_cancel is not None:
            current_task = asyncio.current_task()
            if connection_to_cancel.sender_task is not current_task:
                connection_to_cancel.sender_task.cancel()
                try:
                    await connection_to_cancel.sender_task
                except asyncio.CancelledError:
                    pass
                except Exception:
                    pass

    async def mark_seen(self, user_id: str, connection_id: str) -> None:
        async with self._lock:
            for connection in self._connections_by_user.get(user_id, []):
                if connection.connection_id == connection_id:
                    connection.last_seen_at = time.time()
                    return

    async def count_user_sessions(self, user_id: str) -> int:
        async with self._lock:
            return len(self._connections_by_user.get(user_id, []))

    async def send_to_connection(self, connection_id: str, payload: dict[str, Any]) -> bool:
        async with self._lock:
            connection = self._connections_by_id.get(connection_id)
        if connection is None:
            return False
        connection.outgoing_queue.put_nowait(payload)
        return True

    async def broadcast_to_user(self, user_id: str, payload: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections_by_user.get(user_id, []))
        for connection in connections:
            connection.outgoing_queue.put_nowait(payload)

    async def dispatch_request_to_user(
        self,
        user_id: str,
        message: dict[str, Any],
        timeout_seconds: float,
    ) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        request_id = str(uuid.uuid4())

        async with self._lock:
            connections = self._connections_by_user.get(user_id, [])
            if not connections:
                raise fastapi.HTTPException(status_code=409, detail="No active client websocket session for this user")

            connection = max(connections, key=lambda current: current.last_seen_at)
            future: asyncio.Future[dict[str, Any]] = loop.create_future()
            self._pending_requests[request_id] = PendingClientRequest(
                request_id=request_id,
                connection_id=connection.connection_id,
                future=future,
            )

        try:
            connection.outgoing_queue.put_nowait({
                **message,
                "request_id": request_id,
            })
            return await asyncio.wait_for(future, timeout=timeout_seconds)
        except asyncio.TimeoutError:
            raise fastapi.HTTPException(status_code=504, detail="Timed out waiting for client localhost model response")
        except RuntimeError as exc:
            raise fastapi.HTTPException(status_code=409, detail=str(exc))
        except fastapi.HTTPException:
            raise
        except Exception as exc:
            raise fastapi.HTTPException(status_code=502, detail=f"Failed to send localhost request to client: {exc}")
        finally:
            async with self._lock:
                self._pending_requests.pop(request_id, None)

    async def resolve_request(self, request_id: str, payload: dict[str, Any]) -> bool:
        async with self._lock:
            pending = self._pending_requests.get(request_id)
            if pending is None:
                return False
            if pending.future.done():
                self._pending_requests.pop(request_id, None)
                return False
            pending.future.set_result(payload)
            self._pending_requests.pop(request_id, None)
            return True
