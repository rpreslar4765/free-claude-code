"""Provider wrapper that tries a local model first, falling back when it looks inadequate."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from loguru import logger

from config.settings import Settings
from core.trace import trace_event
from providers.base import BaseProvider

from .heuristics import is_inadequate_response


def _reconstruct_local_text(chunks: list[str]) -> str:
    """Rebuild the assistant's plain-text answer from buffered Anthropic SSE chunks."""
    buffer = "".join(chunks)
    text_parts: list[str] = []
    for line in buffer.splitlines():
        if not line.startswith("data: "):
            continue
        try:
            payload = json.loads(line[len("data: ") :])
        except ValueError:
            continue
        if payload.get("type") != "content_block_delta":
            continue
        delta = payload.get("delta") or {}
        if delta.get("type") == "text_delta":
            text_parts.append(delta.get("text") or "")
    return "".join(text_parts)


class LocalFirstProvider(BaseProvider):
    """Try a local model first; fall back to another provider on an inadequate answer.

    The wrapped local provider is always fully buffered (never streamed straight to
    the client) because judging adequacy requires the complete answer. Accepted
    answers are then replayed verbatim; rejected answers are discarded and the
    fallback provider streams its response normally.
    """

    def __init__(
        self,
        *,
        local: BaseProvider,
        local_model: str,
        fallback: BaseProvider,
        settings: Settings,
    ):
        self._local = local
        self._local_model = local_model
        self._fallback = fallback
        self._settings = settings

    def preflight_stream(
        self, request: Any, *, thinking_enabled: bool | None = None
    ) -> None:
        """Validate against the fallback provider (the request as the router resolved it)."""
        self._fallback.preflight_stream(request, thinking_enabled=thinking_enabled)

    async def cleanup(self) -> None:
        """No-op: the wrapped local/fallback providers are owned by the registry."""
        return None

    async def list_model_ids(self) -> frozenset[str]:
        return await self._fallback.list_model_ids()

    async def stream_response(
        self,
        request: Any,
        input_tokens: int = 0,
        *,
        request_id: str | None = None,
        thinking_enabled: bool | None = None,
    ) -> AsyncIterator[str]:
        local_request = request.model_copy(
            update={"model": self._local_model}, deep=True
        )

        buffered: list[str] = []
        try:
            buffered.extend(
                [
                    chunk
                    async for chunk in self._local.stream_response(
                        local_request,
                        input_tokens,
                        request_id=request_id,
                        thinking_enabled=thinking_enabled,
                    )
                ]
            )
        except Exception as exc:
            logger.warning(
                "Local-first local provider raised, falling back: exc_type={}",
                type(exc).__name__,
            )
            buffered = []

        local_text = _reconstruct_local_text(buffered)
        accepted = not is_inadequate_response(local_text)

        trace_event(
            stage="provider",
            event="provider.local_first.decision",
            source="provider",
            provider="LOCAL_FIRST",
            request_id=request_id,
            local_model=self._local_model,
            accepted=accepted,
        )
        self._log_training_data(
            request=request,
            local_text=local_text,
            accepted=accepted,
            request_id=request_id,
        )

        if accepted:
            for chunk in buffered:
                yield chunk
            return

        async for chunk in self._fallback.stream_response(
            request,
            input_tokens,
            request_id=request_id,
            thinking_enabled=thinking_enabled,
        ):
            yield chunk

    def _log_training_data(
        self,
        *,
        request: Any,
        local_text: str,
        accepted: bool,
        request_id: str | None,
    ) -> None:
        if not self._settings.local_first_log_training_data:
            return
        record = {
            "request_id": request_id,
            "timestamp": time.time(),
            "system": getattr(request, "system", None),
            "messages": request.model_dump(exclude_none=True).get("messages", []),
            "local_model": self._local_model,
            "local_response": local_text,
            "accepted": accepted,
        }
        path = Path(self._settings.local_first_training_data_path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning("Local-first training-data log write failed: {}", exc)
