"""Heuristics for judging whether a local model's answer is adequate."""

# Substrings of the user-facing error messages produced by
# ``core.anthropic.errors.get_user_facing_error_message`` when the local provider's
# *transport* failed (connection refused, timeout, rate limit, etc.) rather than the
# model actually answering. These are embedded as ordinary assistant text by
# ``core.anthropic.provider_stream_error.iter_provider_stream_error_sse_events``, so
# they must be matched the same way as a refusal phrase.
PROVIDER_ERROR_MARKERS: tuple[str, ...] = (
    "provider request timed out",
    "could not connect to provider",
    "provider rate limit reached",
    "provider authentication failed",
    "invalid request sent to provider",
    "provider is currently overloaded",
    "provider api request failed",
    "provider is temporarily unavailable",
    "provider request failed",
)

DEFAULT_REFUSAL_PHRASES: tuple[str, ...] = (
    "i don't know",
    "i do not know",
    "i'm not sure",
    "i am not sure",
    "as an ai language model",
    "i cannot help with that",
    "i can't help with that",
    "i don't have access to",
    "i do not have access to",
    "i'm unable to",
    "i am unable to",
    "i have no information",
)


def is_inadequate_response(
    text: str,
    *,
    refusal_phrases: tuple[str, ...] = DEFAULT_REFUSAL_PHRASES,
) -> bool:
    """Return True when a local model's response should trigger fallback."""
    stripped = text.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    if any(marker in lowered for marker in PROVIDER_ERROR_MARKERS):
        return True
    return any(phrase in lowered for phrase in refusal_phrases)
