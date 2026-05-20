"""HTTP routes for Humanize and Detect."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from humanizer.auth import require_llm_user
from humanizer.engines.llm_polish import LLMPolishError
from humanizer.models import (
    DetectRequest,
    DetectResponse,
    HumanizeLLMResponse,
    HumanizeRequest,
    HumanizeResponse,
)
from humanizer.pipeline import run_detect, run_humanize, run_humanize_llm
from humanizer.settings import get_settings

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["humanizer"])


def _enforce_size(text: str) -> None:
    cap = get_settings().max_text_length
    if len(text) > cap:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"text exceeds MAX_TEXT_LENGTH={cap}",
        )


@router.post("/humanize", response_model=HumanizeResponse)
async def humanize(req: HumanizeRequest) -> HumanizeResponse:
    _enforce_size(req.text)
    return run_humanize(req)


@router.post("/detect", response_model=DetectResponse)
async def detect(req: DetectRequest) -> DetectResponse:
    _enforce_size(req.text)
    return run_detect(req)


@router.post("/humanize/llm", response_model=HumanizeLLMResponse)
async def humanize_llm(
    req: HumanizeRequest,
    _user: Annotated[str, Depends(require_llm_user)],
) -> HumanizeLLMResponse:
    """Statistical pipeline + Gemini Flash 3.5 final polish.

    Gated behind HTTPBasic auth (LLM_USER / LLM_PASSWORD env vars) because
    every call costs money. Returns 503 if not configured, 401 if bad creds,
    502 if Gemini fails.
    """
    _enforce_size(req.text)
    settings = get_settings()
    if not settings.gemini_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="gemini_api_key_not_configured",
        )
    try:
        return await run_humanize_llm(req, settings.gemini_api_key)
    except LLMPolishError as e:
        log.warning("llm_polish_failed", extra={"error": str(e)[:200]})
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"llm_polish_failed: {e}",
        )
