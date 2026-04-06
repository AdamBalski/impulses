from __future__ import annotations

import json
import logging
from typing import Any

import fastapi
import httpx
import pydantic

from src.ai.client_session_registry import ClientSessionRegistry
from src.dao.llm_model_repo import LlmModel, LlmModelRepo, LlmModelSettings


LOCALHOST_MODEL_TIMEOUT_SECONDS = 120.0
UPSTREAM_MODEL_TIMEOUT_SECONDS = 120.0


class LlmChatCompletionResult(pydantic.BaseModel):
    reply: str
    response_model: str | None = None
    raw_response: dict[str, Any] | None = None
    raw_message: dict[str, Any] | None = None
    finish_reason: str | None = None


def _build_chat_completions_url(base_url: str) -> str:
    trimmed = base_url.rstrip("/")
    if trimmed.endswith("/chat/completions"):
        return trimmed
    return f"{trimmed}/chat/completions"


def _extract_message_content(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "text" and isinstance(item.get("text"), str):
                text_parts.append(item["text"])
        return "".join(text_parts)
    return ""


def _normalize_tool_calls(raw_tool_calls: Any) -> list[dict[str, Any]]:
    if isinstance(raw_tool_calls, list):
        return [item for item in raw_tool_calls if isinstance(item, dict)]
    if isinstance(raw_tool_calls, dict):
        return [raw_tool_calls]
    if isinstance(raw_tool_calls, str):
        trimmed = raw_tool_calls.strip()
        if not trimmed:
            return []
        try:
            decoded = json.loads(trimmed)
        except Exception:
            return []
        return _normalize_tool_calls(decoded)
    return []


def _extract_chat_completion_result(payload: dict[str, Any]) -> LlmChatCompletionResult:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise fastapi.HTTPException(status_code=502, detail="LLM response did not include choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise fastapi.HTTPException(status_code=502, detail="LLM response choice had invalid shape")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise fastapi.HTTPException(status_code=502, detail="LLM response did not include a message")

    normalized_message = dict(message)
    tool_calls = _normalize_tool_calls(message.get("tool_calls"))
    if not tool_calls:
        tool_calls = _normalize_tool_calls(message.get("toolCalls"))
    if tool_calls:
        normalized_message["tool_calls"] = tool_calls

    reply = _extract_message_content(normalized_message).strip()
    response_model = payload.get("model")
    if response_model is not None and not isinstance(response_model, str):
        response_model = None

    finish_reason = first_choice.get("finish_reason")
    if finish_reason is not None and not isinstance(finish_reason, str):
        finish_reason = None

    return LlmChatCompletionResult(
        reply=reply,
        response_model=response_model,
        raw_response=payload,
        raw_message=normalized_message,
        finish_reason=finish_reason,
    )


def _extract_error_message(payload: Any, fallback: str) -> str:
    if isinstance(payload, dict):
        for key in ("error", "detail", "message"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                nested = value.get("message")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()
    return fallback


async def _execute_remote_chat_completion(
    settings: LlmModelSettings,
    model: str,
    messages: list[dict[str, str]],
    extra_body: dict[str, Any] | None = None,
) -> LlmChatCompletionResult:
    request_body = {
        "model": model,
        "messages": messages,
    }
    if extra_body:
        request_body.update(extra_body)
    headers = {
        header.name: header.value
        for header in settings.headers
    }

    try:
        async with httpx.AsyncClient(timeout=UPSTREAM_MODEL_TIMEOUT_SECONDS) as client:
            response = await client.post(
                _build_chat_completions_url(settings.base_url),
                headers=headers,
                json=request_body,
            )
    except httpx.TimeoutException:
        raise fastapi.HTTPException(status_code=504, detail="Timed out while calling the model endpoint")
    except httpx.HTTPError as exc:
        raise fastapi.HTTPException(status_code=502, detail=f"Failed to call the model endpoint: {exc}")

    try:
        payload = response.json()
    except ValueError:
        payload = None

    if response.status_code >= 400:
        detail = _extract_error_message(payload, f"Model endpoint returned status {response.status_code}")
        raise fastapi.HTTPException(status_code=502, detail=detail)

    if not isinstance(payload, dict):
        raise fastapi.HTTPException(status_code=502, detail="Model endpoint returned a non-JSON response")

    return _extract_chat_completion_result(payload)


async def _execute_localhost_chat_completion(
    settings: LlmModelSettings,
    model: str,
    messages: list[dict[str, str]],
    extra_body: dict[str, Any] | None = None,
    *,
    user_id: str | None,
    registry: ClientSessionRegistry | None,
) -> LlmChatCompletionResult:
    if not user_id:
        logging.error("Localhost model execution requested without user_id")
        raise fastapi.HTTPException(status_code=500, detail="Internal server error")
    if registry is None:
        logging.error("Localhost model execution requested without client session registry")
        raise fastapi.HTTPException(status_code=500, detail="Internal server error")

    request_body: dict[str, Any] = {
        "model": model,
        "messages": messages,
    }
    if extra_body:
        request_body.update(extra_body)

    payload = await registry.dispatch_request_to_user(
        user_id,
        {
            "type": "llm_request",
            "url": _build_chat_completions_url(settings.base_url),
            "method": "POST",
            "headers": [
                {"name": header.name, "value": header.value}
                for header in settings.headers
            ],
            "body": request_body,
        },
        timeout_seconds=LOCALHOST_MODEL_TIMEOUT_SECONDS,
    )

    if not payload.get("ok"):
        error = payload.get("error")
        if not isinstance(error, str) or not error.strip():
            error = "Localhost model request failed"
        raise fastapi.HTTPException(status_code=502, detail=error.strip())

    data = payload.get("data")
    if not isinstance(data, dict):
        raise fastapi.HTTPException(status_code=502, detail="Localhost model endpoint returned an invalid response")

    return _extract_chat_completion_result(data)


async def execute_chat_completion_from_settings(
    settings: LlmModelSettings,
    model: str,
    messages: list[dict[str, str]],
    extra_body: dict[str, Any] | None = None,
    *,
    user_id: str | None = None,
    registry: ClientSessionRegistry | None = None,
) -> LlmChatCompletionResult:
    trimmed_model = model.strip()
    if not trimmed_model:
        raise fastapi.HTTPException(status_code=422, detail="LLM model is required")
    if not messages:
        raise fastapi.HTTPException(status_code=422, detail="At least one chat message is required")

    if settings.is_localhost:
        return await _execute_localhost_chat_completion(
            settings,
            trimmed_model,
            messages,
            extra_body,
            user_id=user_id,
            registry=registry,
        )

    return await _execute_remote_chat_completion(settings, trimmed_model, messages, extra_body)


async def execute_chat_completion_from_stored_model(
    repo: LlmModelRepo,
    user_id: str,
    model_id: str,
    messages: list[dict[str, str]],
    extra_body: dict[str, Any] | None = None,
    *,
    registry: ClientSessionRegistry | None = None,
) -> tuple[LlmModel, LlmChatCompletionResult]:
    stored_model = repo.get_model_by_id(user_id, model_id)
    if not stored_model:
        raise fastapi.HTTPException(status_code=404, detail="Model not found")

    result = await execute_chat_completion_from_settings(
        stored_model.settings,
        stored_model.model_name,
        messages,
        extra_body,
        user_id=user_id,
        registry=registry,
    )
    return stored_model, result
