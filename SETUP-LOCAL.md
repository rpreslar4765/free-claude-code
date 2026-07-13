# Local Setup — Claude Code + Ollama (qwen3-coder)

Everything below runs on your Windows machine. The proxy is already configured
via the `.env` file in this folder (routes Opus/Sonnet/Haiku → `ollama/qwen3-coder`).

## 1. Install Ollama and pull the model

Download and install from https://ollama.com/download/windows, then:

```powershell
ollama pull qwen3-coder
ollama list   # confirm it's there; Ollama serves on localhost:11434 automatically
```

## 2. Install runtime (one time)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uv self update
uv python install 3.14
```

## 3. Install project dependencies (one time)

```powershell
cd C:\Users\user\Documents\GitHub\free-claude-code
uv sync
```

## 4. Install Claude Code CLI (one time, if not installed)

```powershell
npm install -g @anthropic-ai/claude-code
```

## 5. Start the proxy

```powershell
cd C:\Users\user\Documents\GitHub\free-claude-code
uv run fcc-server
```

Server runs at http://localhost:8082 — Admin UI at http://localhost:8082/admin.
Health check: http://localhost:8082/ should return
`{"status":"ok","provider":"ollama","model":"ollama/qwen3-coder"}`.

## 6. Link Claude Code to it

Easiest — the bundled launcher (starts Claude Code pre-linked to the proxy):

```powershell
cd C:\Users\user\Documents\GitHub\free-claude-code
uv run fcc-claude
```

Or manually, in any terminal:

```powershell
$env:ANTHROPIC_BASE_URL = "http://localhost:8082"
$env:ANTHROPIC_API_KEY  = "local"
claude
```

## Changing the model later

Pull another model (`ollama pull <name>`), then edit `.env` in this folder and
replace `qwen3-coder` with the new name (keep the `ollama/` prefix). Restart
`fcc-server`. Or use the Admin UI at http://localhost:8082/admin.

## Verified (in sandbox, 2026-07-10)

- `uv sync` on Python 3.14: OK
- Test suite: 1354 passed
- Server boot on :8082: OK — health, `/v1/models`, `/v1/messages` (streams), `/admin` all responding
