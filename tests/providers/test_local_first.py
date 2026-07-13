"""Tests for local-first routing (try a local model, fall back when inadequate)."""

import json

import pytest

from api.models.anthropic import Message, MessagesRequest
from config.settings import Settings
from providers.base import BaseProvider, ProviderConfig
from providers.local_first import LocalFirstProvider


def sse_text_event(text: str) -> str:
    """Build a minimal content_block_delta SSE event carrying assistant text."""
    payload = {
        "type": "content_block_delta",
        "index": 0,
        "delta": {"type": "text_delta", "text": text},
    }
    return f"event: content_block_delta\ndata: {json.dumps(payload)}\n\n"


class FakeProvider(BaseProvider):
    """Minimal stand-in for a provider: records calls, yields configured chunks."""

    def __init__(
        self, chunks: list[str] | None = None, *, raises: Exception | None = None
    ):
        super().__init__(ProviderConfig(api_key="fake"))
        self.chunks = chunks or []
        self.raises = raises
        self.stream_calls: list[dict] = []
        self.preflight_calls: list[dict] = []

    def preflight_stream(self, request, *, thinking_enabled=None):
        self.preflight_calls.append(
            {"request": request, "thinking_enabled": thinking_enabled}
        )

    async def stream_response(
        self, request, input_tokens=0, *, request_id=None, thinking_enabled=None
    ):
        self.stream_calls.append(
            {
                "request": request,
                "input_tokens": input_tokens,
                "request_id": request_id,
                "thinking_enabled": thinking_enabled,
            }
        )
        if self.raises is not None:
            raise self.raises
        for chunk in self.chunks:
            yield chunk

    async def list_model_ids(self):
        return frozenset({"fake-model"})

    async def cleanup(self):
        return None


@pytest.fixture
def request_data():
    return MessagesRequest(
        model="fallback/model",
        messages=[Message(role="user", content="What is 2+2?")],
        system="be helpful",
    )


@pytest.fixture
def settings(tmp_path, monkeypatch):
    # Aliased Settings fields only accept their env var name (not the Python
    # attribute name) unless populate_by_name is set, so override via env like the
    # rest of the test suite (see tests/config/test_config.py).
    monkeypatch.setitem(Settings.model_config, "env_file", ())
    monkeypatch.setenv("LOCAL_FIRST_LOG_TRAINING_DATA", "false")
    monkeypatch.setenv(
        "LOCAL_FIRST_TRAINING_DATA_PATH", str(tmp_path / "training.jsonl")
    )
    return Settings()


@pytest.mark.asyncio
async def test_accepted_local_response_is_replayed_without_fallback(
    request_data, settings
):
    """A confident local answer is streamed back verbatim; fallback is never called."""
    local_chunks = [sse_text_event("The answer is 4.")]
    local = FakeProvider(local_chunks)
    fallback = FakeProvider([sse_text_event("fallback answer")])

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    events = [
        event
        async for event in provider.stream_response(request_data, 10, request_id="REQ1")
    ]

    assert events == local_chunks
    assert len(local.stream_calls) == 1
    assert local.stream_calls[0]["request"].model == "qwen3-coder:latest"
    assert fallback.stream_calls == []


@pytest.mark.asyncio
async def test_refusal_phrase_triggers_fallback(request_data, settings):
    """A local refusal ("I don't know") falls back and streams the fallback's chunks."""
    local = FakeProvider([sse_text_event("I don't know the answer to that.")])
    fallback_chunks = [sse_text_event("The answer is 4.")]
    fallback = FakeProvider(fallback_chunks)

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    events = [event async for event in provider.stream_response(request_data, 10)]

    assert events == fallback_chunks
    assert len(fallback.stream_calls) == 1
    # Fallback receives the original request untouched (real provider/model).
    assert fallback.stream_calls[0]["request"] is request_data


@pytest.mark.asyncio
async def test_local_provider_error_triggers_fallback(request_data, settings):
    """If the local provider raises outright, fall back instead of failing the request."""
    local = FakeProvider(raises=ConnectionError("local model unreachable"))
    fallback_chunks = [sse_text_event("fallback answer")]
    fallback = FakeProvider(fallback_chunks)

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    events = [event async for event in provider.stream_response(request_data, 10)]

    assert events == fallback_chunks


@pytest.mark.asyncio
async def test_embedded_provider_error_text_triggers_fallback(request_data, settings):
    """A transport failure embedded as SSE text (real Ollama behavior) also falls back."""
    local = FakeProvider([sse_text_event("Provider API request failed.")])
    fallback_chunks = [sse_text_event("fallback answer")]
    fallback = FakeProvider(fallback_chunks)

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    events = [event async for event in provider.stream_response(request_data, 10)]

    assert events == fallback_chunks


@pytest.mark.asyncio
async def test_training_data_logged_when_enabled(request_data, tmp_path, monkeypatch):
    """Accept/reject decisions are appended as JSON lines when logging is enabled."""
    log_path = tmp_path / "training.jsonl"
    monkeypatch.setitem(Settings.model_config, "env_file", ())
    monkeypatch.setenv("LOCAL_FIRST_LOG_TRAINING_DATA", "true")
    monkeypatch.setenv("LOCAL_FIRST_TRAINING_DATA_PATH", str(log_path))
    settings = Settings()
    local = FakeProvider([sse_text_event("The answer is 4.")])
    fallback = FakeProvider([])

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    [
        event
        async for event in provider.stream_response(request_data, 10, request_id="REQ1")
    ]

    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["request_id"] == "REQ1"
    assert record["accepted"] is True
    assert record["local_response"] == "The answer is 4."
    assert record["local_model"] == "qwen3-coder:latest"


@pytest.mark.asyncio
async def test_training_data_not_logged_when_disabled(request_data, settings):
    """No file is written when LOCAL_FIRST_LOG_TRAINING_DATA is off."""
    local = FakeProvider([sse_text_event("The answer is 4.")])
    fallback = FakeProvider([])

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    [event async for event in provider.stream_response(request_data, 10)]

    assert not settings.local_first_log_training_data
    from pathlib import Path

    assert not Path(settings.local_first_training_data_path).exists()


def test_preflight_delegates_to_fallback(request_data, settings):
    """preflight_stream validates against the fallback provider, not the local one."""
    local = FakeProvider([])
    fallback = FakeProvider([])

    provider = LocalFirstProvider(
        local=local,
        local_model="qwen3-coder:latest",
        fallback=fallback,
        settings=settings,
    )

    provider.preflight_stream(request_data, thinking_enabled=True)

    assert len(fallback.preflight_calls) == 1
    assert local.preflight_calls == []
