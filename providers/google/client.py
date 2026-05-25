"""Google Gemini provider implementation."""

from typing import Any

from providers.base import ProviderConfig
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body

GOOGLE_DEFAULT_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"


class GoogleProvider(OpenAIChatTransport):
    """Google Gemini provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="GOOGLE",
            base_url=config.base_url or GOOGLE_DEFAULT_BASE,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build request body for Google Gemini."""
        if thinking_enabled is None:
            thinking_enabled = self._is_thinking_enabled(request)
        return build_request_body(
            request,
            thinking_enabled=thinking_enabled,
        )
