"""HTTPBasic auth gate for the LLM-mode endpoint.

Single-user, env-driven. Credentials live in Coolify secrets:
  - LLM_USER
  - LLM_PASSWORD

The /api/humanize endpoint and detector remain open. Only LLM mode is gated
because it costs money per call (Gemini API).

Comparison uses `hmac.compare_digest` to mitigate timing attacks.
"""

from __future__ import annotations

import hmac
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from humanizer.settings import get_settings

# auto_error=False so we can return 503 (not configured) before 401 (bad creds).
_security = HTTPBasic(realm="Humanize LLM Mode", auto_error=False)


def require_llm_user(
    creds: Annotated[HTTPBasicCredentials | None, Depends(_security)],
) -> str:
    """Validates HTTPBasic creds against env-stored LLM_USER / LLM_PASSWORD.

    Order of failures (matters for the frontend UX):
      1. 503 if LLM mode is not configured (no env vars)
      2. 401 if missing or wrong credentials
    """
    settings = get_settings()
    if not settings.llm_user or not settings.llm_password:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="llm_mode_not_configured",
        )

    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing_credentials",
            headers={"WWW-Authenticate": 'Basic realm="Humanize LLM Mode"'},
        )

    expected_user = settings.llm_user.encode("utf-8")
    expected_pass = settings.llm_password.encode("utf-8")
    got_user = (creds.username or "").encode("utf-8")
    got_pass = (creds.password or "").encode("utf-8")

    user_ok = hmac.compare_digest(got_user, expected_user)
    pass_ok = hmac.compare_digest(got_pass, expected_pass)

    if not (user_ok and pass_ok):
        # Constant-time second compare to flatten timing regardless of which
        # field was wrong.
        _ = secrets.compare_digest("a", "a")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid_credentials",
            headers={"WWW-Authenticate": 'Basic realm="Humanize LLM Mode"'},
        )
    return creds.username
