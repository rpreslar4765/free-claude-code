# 50-Agent Code Repair Router Skill

Use this skill first in GitHub repos. Do not call all agents. Call only the one agent, or the smallest safe team of agents, needed for the exact task.

## Hard rule

Select the minimum agent scope. Never run broad repairs when a specialist can handle the issue.

## Agent catalog

- `repo-router` — Repository Router: Choose the correct specialist agent or smallest safe agent team based on repo type and failure area.
- `python-repair` — Python Repair Agent: Repair Python packaging, imports, syntax, pytest, venvs, and dependency issues.
- `node-react-repair` — Node React Repair Agent: Repair Node, npm, Vite, React, Next.js, TypeScript, and package scripts.
- `typescript-repair` — TypeScript Repair Agent: Repair TypeScript configs, compiler errors, types, ESLint, and build issues.
- `powershell-repair` — PowerShell Repair Agent: Repair PowerShell scripts, execution policy notes, paths, modules, and Windows automation.
- `dataflex-odbc` — DataFlex ODBC Agent: Repair and validate DataFlex, ODBC DSN, pyodbc, .dat, .k1-.k5, and backend read-only access.
- `sql-safety` — SQL Safety Agent: Review SQL queries for injection, allow-listing, read-only checks, migrations, and schema safety.
- `ollama-local-ai` — Ollama Local AI Agent: Configure Ollama/Llama3 local review and local model-assisted repository analysis.
- `claude-code-proxy` — Claude Code Proxy Agent: Repair Claude Code, free-claude-code proxy settings, and Anthropic-compatible local providers.
- `github-actions-ci` — GitHub Actions CI Agent: Repair workflows, test matrices, actions versions, artifacts, and status checks.
- `codespaces` — GitHub Codespaces Agent: Repair devcontainers, Codespace bootstrap scripts, Node/Python environments, and workspace setup.
- `docker-repair` — Docker Repair Agent: Repair Dockerfiles, compose files, build contexts, health checks, and container test commands.
- `windows-env` — Windows Environment Agent: Repair Windows PATH, Python, Node, PowerShell, Git, gh, npm, and Ollama environment issues.
- `wsl-linux-env` — WSL Linux Environment Agent: Repair WSL Ubuntu, permissions, npm prefix, Node, Python, Docker, and Linux tooling.
- `requirements-manager` — Requirements Manager Agent: Fix requirements.txt, pyproject.toml, package.json, lockfiles, and dependency pinning.
- `test-runner` — Test Runner Agent: Run and repair pytest, npm test, ctest, dotnet test, integration markers, and reports.
- `lint-format` — Lint Format Agent: Apply safe formatting via Ruff, Black, isort, ESLint, Prettier, clang-format, and dotnet format.
- `security-auditor` — Security Auditor Agent: Review code for secrets, injection, unsafe subprocess, path traversal, and dependency risk.
- `secrets-guard` — Secrets Guard Agent: Detect and prevent committed tokens, API keys, DSNs, passwords, .env leaks, and local secrets.
- `readme-docs` — README Docs Agent: Create and repair README, quickstart, install, runbook, and troubleshooting docs.
- `reader-report` — Reader Report Agent: Generate plain-English repair reports for owners, IT staff, and non-developers.
- `api-integration` — API Integration Agent: Repair REST clients, API auth patterns, retry logic, rate limits, and safe error handling.
- `shopify-fiztrade` — Shopify FIZTrade Agent: Repair Shopify/FIZTrade sync code, API mapping, product payloads, and retry workflows.
- `pawnpay-sync` — PawnPay Sync Agent: Repair Pawnpay, pps-sync, customer/ticket/payment sync, and sync verification logic.
- `pawndex-dashboard` — Pawndex Dashboard Agent: Repair Pawndex dashboard, Flask/FastAPI views, search, payment buttons, and reports.
- `database-schema` — Database Schema Agent: Review and repair schemas, indexes, migrations, models, and data access layers.
- `flask-fastapi` — Flask FastAPI Agent: Repair Flask/FastAPI apps, routes, uvicorn/gunicorn, templates, and API responses.
- `frontend-ui` — Frontend UI Agent: Repair UI layout, React components, CSS/Tailwind, accessibility, and user flows.
- `build-release` — Build Release Agent: Repair builds, packaging, releases, artifacts, versioning, and GitHub release workflows.
- `git-repair` — Git Repair Agent: Repair branches, remotes, merge conflicts, submodules, .gitignore, and PR workflows.
- `repo-cleanup` — Repo Cleanup Agent: Identify safe cleanup targets: caches, generated files, duplicate artifacts, and oversized folders.
- `windows-service` — Windows Service Agent: Repair Windows scheduled tasks, services, NSSM wrappers, logs, and restart behavior.
- `odbc-driver` — ODBC Driver Agent: Repair ODBC driver detection, DSN setup, bitness mismatch, pyodbc connection strings, and diagnostics.
- `network-diagnostics` — Network Diagnostics Agent: Diagnose API/network/DNS/proxy/port connectivity without changing production network settings.
- `logging-observability` — Logging Observability Agent: Repair logging, structured logs, error reports, Sentry-style handling, and diagnostics.
- `error-triage` — Error Triage Agent: Analyze stack traces and route to the correct repair agent or agent team.
- `dependency-upgrade` — Dependency Upgrade Agent: Plan safe dependency upgrades, incompatible packages, Python versions, and Node versions.
- `python37-compat` — Python 3.7 Compatibility Agent: Repair Python 3.7/PyPy compatibility, old syntax, futures, typing, and backports.
- `cpp-cmake` — C++ CMake Agent: Repair C++/CMake builds, compiler flags, clang-format, and ctest workflows.
- `csharp-dotnet` — C# Dotnet Agent: Repair .NET builds, csproj/sln, dotnet restore/build/test, and formatting.
- `browser-automation` — Browser Automation Agent: Repair Playwright/Selenium style test setup, browser deps, and UI smoke tests.
- `devcontainer` — Devcontainer Agent: Repair .devcontainer setup, features, postCreateCommand, and Codespaces resources.
- `npm-permissions` — NPM Permissions Agent: Repair npm EACCES, WSL/Windows UNC path issues, npm global prefix, and Node installation.
- `gemini-cli` — Gemini CLI Agent: Repair Gemini CLI setup, environment checks, and local command troubleshooting.
- `github-cli` — GitHub CLI Agent: Repair gh auth, repo clone/pull, PR creation, workflow status checks, and release commands.
- `data-migration` — Data Migration Agent: Plan safe migrations, backups, dry-runs, validation, and rollback notes.
- `backup-restore` — Backup Restore Agent: Create safe backup/restore plans before repair, cleanup, or migration tasks.
- `performance-profiler` — Performance Profiler Agent: Find slow tests/builds/scripts, large dependencies, cache strategy, and resource bottlenecks.
- `compliance-audit` — Compliance Audit Agent: Review audit-sensitive workflows, police uploads, data handling, and reporting safeguards.
- `final-verifier` — Final Verifier Agent: Run final verification, summarize pass/fail state, and produce merge-ready checklist.

## Default teams

- Python package failure: `python-repair`, `requirements-manager`, `test-runner`, `final-verifier`
- React/Codespace failure: `node-react-repair`, `codespaces`, `npm-permissions`, `final-verifier`
- DataFlex backend: `dataflex-odbc`, `odbc-driver`, `sql-safety`, `secrets-guard`, `final-verifier`
- Local AI/Ollama: `ollama-local-ai`, `claude-code-proxy`, `windows-env` or `wsl-linux-env`
- GitHub CI failure: `github-actions-ci`, `test-runner`, `requirements-manager`, `final-verifier`
- Security review: `security-auditor`, `secrets-guard`, `sql-safety`, `final-verifier`

## Required output

1. Agents selected
2. Why selected
3. Commands to run
4. Files changed
5. Tests/checks run
6. Remaining risks
7. Final pass/fail
