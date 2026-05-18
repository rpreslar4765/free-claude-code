# Copilot Instructions

## Commands

Always use `uv run` — never the global `python` command.

```bash
uv run ruff format          # format
uv run ruff check           # lint
uv run ty check             # type-check (no # type: ignore or # ty: ignore allowed)
uv run pytest               # full test suite (runs in parallel with -n auto)
uv run pytest tests/path/to/test_file.py::test_name  # single test
```

Run in that order before pushing. All five CI checks must pass: **Ban type ignore suppressions**, **ruff-format**, **ruff-check**, **ty**, **pytest**.

Live/smoke tests are opt-in only (they touch real services or require interaction) and are gated by markers like `live`, `provider`, `messaging`, `cli`, `voice`. The default `uv run pytest` run skips them.

## Architecture

`free-claude-code` is a FastAPI proxy that translates Anthropic Messages API traffic from Claude Code into requests for various model backends.

**Request flow:**
1. Claude Code sends an Anthropic-style request to the proxy (`/v1/messages`, `/v1/messages/count_tokens`, `/v1/models`).
2. `api/routes.py` + `api/services.py` handle ingress. `api/optimization_handlers.py` short-circuits trivial Claude Code probes locally (network probes, title generation, etc.) to save latency and quota.
3. `api/model_router.py` resolves the Claude model tier (`claude-opus-*`, `claude-sonnet-*`, `claude-haiku-*`) to a configured `provider_type/model_id` slug via `MODEL_OPUS`, `MODEL_SONNET`, `MODEL_HAIKU`, or fallback `MODEL`.
4. `providers/registry.py` looks up or creates the provider instance. The registry also caches model lists for the `/v1/models` gateway model picker.
5. The provider sends the request upstream and streams back an Anthropic-format SSE response.

**Two transport base classes** (extend the right one when adding a provider):
- `OpenAIChatTransport` — translates OpenAI chat-completions streaming into Anthropic SSE. Used by: NVIDIA NIM, Kimi, OpenCode Zen, Z.ai, Fireworks.
- `AnthropicMessagesTransport` — speaks native Anthropic Messages. Used by: Wafer, OpenRouter, DeepSeek, LM Studio, llama.cpp, Ollama.

**Adding a provider requires changes in three places:**
1. `config/provider_catalog.py` — add a `ProviderDescriptor` entry with credential, URL, and proxy attributes.
2. `providers/registry.py` — add a factory function and register it in `PROVIDER_FACTORIES`. `PROVIDER_DESCRIPTORS`, `PROVIDER_FACTORIES`, and `SUPPORTED_PROVIDER_IDS` must all stay in sync (an `AssertionError` is raised at import time if they diverge).
3. `providers/<new_provider>/` — implement the provider class extending the appropriate transport.

**Shared protocol helpers** live in `core/anthropic/`. Never import from one provider's module into another provider.

**Settings** flow: `config/settings.py` (`pydantic-settings`) reads from `.env` / environment. The Admin UI at `/admin` is the intended way to change managed settings at runtime; do not edit the `.env` file by hand during normal operation.

**Messaging** (`messaging/`) implements Discord and Telegram bot wrappers. Add new platforms by implementing the `MessagingPlatform` interface.

## Key Conventions

- **Python 3.14** — the `except TypeError, ValueError:` syntax (multiple exception types without parentheses) is valid and used. Do not add parentheses.
- **Model slug format**: `provider_type/model_id` (e.g., `nvidia_nim/z-ai/glm4.7`, `open_router/deepseek/deepseek-r1-0528:free`).
- **No type suppression**: never add `# type: ignore` or `# ty: ignore` — fix the underlying type issue instead.
- **Provider-specific fields** (e.g., `nim_settings`) belong in the provider's constructor, not in the shared `ProviderConfig`.
- **Encapsulation**: use accessor methods like `set_current_task()` for internal state; do not assign to `_attributes` directly from outside a class.
- **Performance**: accumulate strings into a list and `"".join()` at the end — no `+=` in loops; cache env vars at `__init__` time.
- **AGENTS.md and CLAUDE.md are identical** — keep them in sync when editing either.
- **Tests**: tests are isolated from the `.env` file via `conftest.py` monkeypatching. The `conftest.py` sets mock env vars before any `Settings` imports. Add tests for new changes including edge cases.
- **Dead code**: remove unused code and hardcoded literals; use `settings.*` instead (e.g., `settings.provider_type` not `"nvidia_nim"`).
- **Platform-agnostic naming**: use generic names in shared code (e.g., `PLATFORM_EDIT` not `TELEGRAM_EDIT`).
