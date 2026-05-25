"""Tests for Google Gemini provider."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from providers.base import ProviderConfig
from providers.google import GOOGLE_DEFAULT_BASE, GoogleProvider


class MockMessage:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class MockRequest:
    def __init__(self, **kwargs):
        self.model = "gemini-2.5-flash"
        self.messages = [MockMessage("user", "Hello")]
        self.max_tokens = 100
        self.temperature = 0.5
        self.top_p = 0.9
        self.system = "System prompt"
        self.stop_sequences = None
        self.tools = []
        self.extra_body = {}
        self.thinking = MagicMock()
        self.thinking.enabled = True
        for key, value in kwargs.items():
            setattr(self, key, value)


@pytest.fixture
def google_config():
    return ProviderConfig(
        api_key="test_google_key",
        base_url=GOOGLE_DEFAULT_BASE,
        rate_limit=10,
        rate_window=60,
        enable_thinking=True,
    )


@pytest.fixture(autouse=True)
def mock_rate_limiter():
    """Mock the global rate limiter to prevent waiting."""

    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.openai_compat.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


@pytest.fixture
def google_provider(google_config):
    return GoogleProvider(google_config)


def test_init(google_config):
    """Test provider initialization."""
    with patch("providers.openai_compat.AsyncOpenAI") as mock_openai:
        provider = GoogleProvider(google_config)
        assert provider._api_key == "test_google_key"
        assert provider._base_url == GOOGLE_DEFAULT_BASE
        mock_openai.assert_called_once()


def test_base_url_constant():
    """GOOGLE_DEFAULT_BASE points to the Google Gemini OpenAI endpoint."""
    assert GOOGLE_DEFAULT_BASE == "https://generativelanguage.googleapis.com/v1beta/openai"


def test_build_request_body_basic(google_provider):
    """Basic request body conversion works for Google Gemini."""
    req = MockRequest()
    body = google_provider._build_request_body(req)

    assert body["model"] == "gemini-2.5-flash"
    assert body["messages"][0]["role"] == "system"


def test_build_request_body_global_disable_blocks_thinking():
    """Global disable suppresses provider-side thinking."""
    provider = GoogleProvider(
        ProviderConfig(
            api_key="test_google_key",
            base_url=GOOGLE_DEFAULT_BASE,
            rate_limit=10,
            rate_window=60,
            enable_thinking=False,
        )
    )
    req = MockRequest()
    body = provider._build_request_body(req)

    assert "extra_body" not in body or "thinking" not in body.get("extra_body", {})


def test_build_request_body_request_disable_blocks_thinking(google_provider):
    """Request-level disable suppresses provider-side thinking when global is enabled."""
    req = MockRequest()
    req.thinking.enabled = False
    body = google_provider._build_request_body(req)

    assert "extra_body" not in body or "thinking" not in body.get("extra_body", {})


def test_build_request_body_preserves_caller_extra_body(google_provider):
    """Caller-provided extra_body should be preserved."""
    req = MockRequest(
        extra_body={"custom_param": "value"},
    )
    body = google_provider._build_request_body(req)

    assert body["extra_body"]["custom_param"] == "value"


@pytest.mark.asyncio
async def test_stream_response_text(google_provider):
    """Text content deltas are emitted as text blocks."""
    req = MockRequest()

    mock_chunk = MagicMock()
    mock_chunk.choices = [
        MagicMock(
            delta=MagicMock(
                content="Hello back!",
                reasoning_content=None,
                tool_calls=None,
            ),
            finish_reason="stop",
        )
    ]
    mock_chunk.usage = MagicMock(completion_tokens=5, prompt_tokens=10)

    async def mock_stream():
        yield mock_chunk

    with patch.object(
        google_provider._client.chat.completions, "create", new_callable=AsyncMock
    ) as mock_create:
        mock_create.return_value = mock_stream()

        events = [event async for event in google_provider.stream_response(req)]

        assert any(
            '"text_delta"' in event and "Hello back!" in event for event in events
        )


@pytest.mark.asyncio
async def test_cleanup(google_provider):
    """cleanup closes the OpenAI client."""
    google_provider._client = AsyncMock()

    await google_provider.cleanup()

    google_provider._client.close.assert_called_once()
