"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from humanizer import __version__
from humanizer.logging_setup import AccessLogMiddleware, configure_logging
from humanizer.rate_limit import RateLimitMiddleware
from humanizer.routes import router as api_router
from humanizer.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    import time

    configure_logging()
    settings = get_settings()
    log = logging.getLogger("startup")
    log.info(
        "api_started",
        extra={"route": "/", "method": "STARTUP"},
    )
    log.info(
        f"env={settings.app_env} max_text_length={settings.max_text_length} "
        f"synthid={settings.enable_synthid}"
    )

    # Warm-load dictionaries + frequency lists so the first request is fast.
    t0 = time.perf_counter()
    from humanizer.engines import detector_statistical

    detector_statistical.compute_all("warm up", "en")
    detector_statistical.compute_all("חימום", "he")
    log.info(
        "warm_load_done",
        extra={"latency_ms": round((time.perf_counter() - t0) * 1000, 2)},
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Humanize API",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.web_origin] if settings.web_origin != "*" else ["*"],
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["x-request-id"],
    )
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(RateLimitMiddleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    app.include_router(api_router)
    return app


app = create_app()
