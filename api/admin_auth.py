"""Session cookie helpers for the local admin UI login.

The session token is signed with the currently configured admin password
(``ANTHROPIC_AUTH_TOKEN``) instead of a separate server secret, so rotating
the password automatically invalidates every previously issued session with
no server-side session store to manage.
"""

from __future__ import annotations

import hashlib
import hmac
import time

from fastapi import Response

SESSION_COOKIE_NAME = "fcc_admin_session"
SESSION_TTL_SECONDS = 12 * 60 * 60


def _signature(token: str, issued_at: int) -> str:
    return hmac.new(
        token.encode("utf-8"), str(issued_at).encode("utf-8"), hashlib.sha256
    ).hexdigest()


def create_session_value(token: str) -> str:
    """Build a signed ``issued_at.signature`` session token for ``token``."""
    issued_at = int(time.time())
    return f"{issued_at}.{_signature(token, issued_at)}"


def verify_session_value(value: str, token: str) -> bool:
    """Return whether ``value`` is an unexpired session signed with ``token``."""
    issued_at_str, _, signature = value.partition(".")
    if not signature:
        return False
    try:
        issued_at = int(issued_at_str)
    except ValueError:
        return False
    if time.time() - issued_at > SESSION_TTL_SECONDS:
        return False
    return hmac.compare_digest(signature, _signature(token, issued_at))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        create_session_value(token),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
        path="/admin",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/admin")
