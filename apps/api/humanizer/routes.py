"""HTTP routes for Humanize and Detect."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from humanizer.models import (
    DetectRequest,
    DetectResponse,
    HumanizeRequest,
    HumanizeResponse,
)
from humanizer.pipeline import run_detect, run_humanize
from humanizer.settings import get_settings

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
