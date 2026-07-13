"""Local admin UI routes and APIs."""

from __future__ import annotations

import inspect
import ipaddress
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from config.settings import Settings
from config.settings import get_settings as get_cached_settings
from providers.registry import ProviderRegistry

from .admin_auth import (
    SESSION_COOKIE_NAME,
    clear_session_cookie,
    set_session_cookie,
    verify_session_value,
)
from .admin_config import (
    FIELD_BY_KEY,
    load_config_response,
    provider_config_status,
    validate_updates,
    write_managed_env,
)
from .admin_urls import local_admin_url

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "admin_static"
LOCAL_PROVIDER_PATHS = {
    "lmstudio": "/models",
    "llamacpp": "/models",
    "ollama": "/api/tags",
}


class AdminConfigPayload(BaseModel):
    """Partial config update submitted by the admin UI."""

    values: dict[str, Any] = Field(default_factory=dict)


class AdminLoginPayload(BaseModel):
    """Admin login submission."""

    password: str


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _origin_is_local(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlsplit(origin)
    return _is_loopback_host(parsed.hostname)


def require_loopback_admin(request: Request) -> None:
    """Allow admin access only from the local machine."""

    client_host = request.client.host if request.client else None
    if not _is_loopback_host(client_host):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")

    origin = request.headers.get("origin")
    if not _origin_is_local(origin):
        raise HTTPException(status_code=403, detail="Admin UI is local-only")


def require_admin_session(request: Request) -> None:
    """Require loopback access, and a valid login session once a password is set.

    ``ANTHROPIC_AUTH_TOKEN`` doubles as the admin login password. While it is
    unset, the admin UI stays freely accessible from loopback (matching prior
    behavior); once it is configured, every admin data/action route requires a
    signed session cookie obtained via ``POST /admin/api/login``.
    """

    require_loopback_admin(request)
    token = get_cached_settings().anthropic_auth_token
    if not token:
        return

    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    if not cookie or not verify_session_value(cookie, token):
        raise HTTPException(status_code=401, detail="Admin login required")


def _asset_response(filename: str) -> FileResponse:
    path = STATIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return FileResponse(path)


@router.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    require_loopback_admin(request)
    return _asset_response("index.html")


@router.get("/admin/assets/{filename}", include_in_schema=False)
async def admin_asset(filename: str, request: Request):
    require_loopback_admin(request)
    if filename not in {"admin.css", "admin.js"}:
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return _asset_response(filename)


@router.get("/admin/api/session")
async def admin_session(request: Request):
    require_loopback_admin(request)
    token = get_cached_settings().anthropic_auth_token
    configured = bool(token)
    cookie = request.cookies.get(SESSION_COOKIE_NAME)
    authenticated = not configured or bool(
        cookie and verify_session_value(cookie, token)
    )
    return {"authenticated": authenticated, "configured": configured}


@router.post("/admin/api/login")
async def admin_login(payload: AdminLoginPayload, request: Request, response: Response):
    require_loopback_admin(request)
    token = get_cached_settings().anthropic_auth_token
    if not token:
        raise HTTPException(
            status_code=409, detail="No admin password is configured yet"
        )
    if not secrets.compare_digest(
        payload.password.encode("utf-8"), token.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="Incorrect password")
    set_session_cookie(response, token)
    return {"authenticated": True}


@router.post("/admin/api/logout")
async def admin_logout(request: Request, response: Response):
    require_loopback_admin(request)
    clear_session_cookie(response)
    return {"authenticated": False}


@router.get("/admin/api/config")
async def get_admin_config(request: Request):
    require_admin_session(request)
    return load_config_response()


@router.post("/admin/api/config/validate")
async def validate_admin_config(payload: AdminConfigPayload, request: Request):
    require_admin_session(request)
    return validate_updates(_filtered_values(payload.values))


@router.post("/admin/api/config/apply")
async def apply_admin_config(
    payload: AdminConfigPayload,
    request: Request,
    background_tasks: BackgroundTasks,
):
    require_admin_session(request)
    result = write_managed_env(_filtered_values(payload.values))
    if not result["applied"]:
        return result

    get_cached_settings.cache_clear()
    restart = _restart_metadata(result["pending_fields"], request)
    result["restart"] = restart
    if restart["required"] and restart["automatic"]:
        callback = request.app.state.admin_restart_callback
        background_tasks.add_task(_invoke_admin_restart_callback, callback)
        request.app.state.admin_pending_fields = []
        return result

    old_registry = getattr(request.app.state, "provider_registry", None)
    if isinstance(old_registry, ProviderRegistry):
        await old_registry.cleanup()
    request.app.state.provider_registry = ProviderRegistry()
    request.app.state.admin_pending_fields = result["pending_fields"]
    return result


@router.get("/admin/api/status")
async def admin_status(request: Request):
    require_admin_session(request)
    settings = get_cached_settings()
    registry = getattr(request.app.state, "provider_registry", None)
    cached_models: dict[str, list[str]] = {}
    if isinstance(registry, ProviderRegistry):
        cached_models = {
            provider_id: sorted(model_ids)
            for provider_id, model_ids in registry.cached_model_ids().items()
        }
    return {
        "status": "running",
        "host": settings.host,
        "port": settings.port,
        "model": settings.model,
        "provider": settings.provider_type,
        "pending_fields": getattr(request.app.state, "admin_pending_fields", []),
        "provider_status": provider_config_status(),
        "cached_models": cached_models,
    }


@router.get("/admin/api/providers/local-status")
async def local_provider_status(request: Request):
    require_admin_session(request)
    config = load_config_response()
    values = {field["key"]: field["value"] for field in config["fields"]}
    checks = []
    for provider_id, path in LOCAL_PROVIDER_PATHS.items():
        base_url = _local_provider_url(provider_id, values)
        checks.append(await _check_local_provider(provider_id, base_url, path))
    return {"providers": checks}


@router.post("/admin/api/providers/{provider_id}/test")
async def test_provider(provider_id: str, request: Request):
    require_admin_session(request)
    settings = get_cached_settings()
    registry = getattr(request.app.state, "provider_registry", None)
    if not isinstance(registry, ProviderRegistry):
        registry = ProviderRegistry()
        request.app.state.provider_registry = registry
    try:
        provider = registry.get(provider_id, settings)
        infos = await provider.list_model_infos()
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "ok": False,
            "error_type": type(exc).__name__,
        }
    registry.cache_model_infos(provider_id, infos)
    return {
        "provider_id": provider_id,
        "ok": True,
        "models": sorted(info.model_id for info in infos),
    }


@router.post("/admin/api/models/refresh")
async def refresh_models(request: Request):
    require_admin_session(request)
    settings = get_cached_settings()
    registry = getattr(request.app.state, "provider_registry", None)
    if not isinstance(registry, ProviderRegistry):
        registry = ProviderRegistry()
        request.app.state.provider_registry = registry
    await registry.refresh_model_list_cache(settings)
    return {
        "cached_models": {
            provider_id: sorted(model_ids)
            for provider_id, model_ids in registry.cached_model_ids().items()
        }
    }


def _filtered_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in FIELD_BY_KEY}


async def _invoke_admin_restart_callback(callback: Any) -> None:
    result = callback()
    if inspect.isawaitable(result):
        await result


def _restart_metadata(fields: list[str], request: Request) -> dict[str, Any]:
    callback = getattr(request.app.state, "admin_restart_callback", None)
    automatic = bool(fields and callable(callback))
    return {
        "required": bool(fields),
        "automatic": automatic,
        "admin_url": _next_admin_url() if automatic else None,
        "fields": fields,
    }


def _next_admin_url() -> str:
    fields = {
        field["key"]: field["value"] for field in load_config_response()["fields"]
    }
    settings = Settings.model_construct(
        host=fields.get("HOST") or "0.0.0.0",
        port=int(fields.get("PORT") or 8082),
    )
    return local_admin_url(settings)


def _local_provider_url(provider_id: str, values: dict[str, str]) -> str:
    if provider_id == "lmstudio":
        return values.get("LM_STUDIO_BASE_URL", "")
    if provider_id == "llamacpp":
        return values.get("LLAMACPP_BASE_URL", "")
    if provider_id == "ollama":
        return values.get("OLLAMA_BASE_URL", "")
    return ""


async def _check_local_provider(
    provider_id: str, base_url: str, path: str
) -> dict[str, Any]:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        return {
            "provider_id": provider_id,
            "status": "missing_url",
            "label": "Missing URL",
            "base_url": base_url,
        }

    url = f"{clean_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(url)
        ok = 200 <= response.status_code < 300
        return {
            "provider_id": provider_id,
            "status": "reachable" if ok else "offline",
            "label": "Reachable" if ok else "Offline",
            "base_url": base_url,
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "status": "offline",
            "label": "Offline",
            "base_url": base_url,
            "error_type": type(exc).__name__,
        }
