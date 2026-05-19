"""In-memory sliding-window per-IP rate limiter.

Single-process only — for multi-worker uvicorn the limit applies per worker.
Acceptable for the Coolify single-host deployment topology.
"""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from humanizer.settings import get_settings


class SlidingWindowLimiter:
    """Per-key fixed-capacity sliding window."""

    def __init__(self, capacity: int, window_seconds: float) -> None:
        self.capacity = capacity
        self.window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str, now: float | None = None) -> tuple[bool, float]:
        """Return ``(allowed, retry_after_seconds)``.

        ``retry_after_seconds`` is meaningful only when ``allowed=False``.
        """
        now = now if now is not None else time.monotonic()
        with self._lock:
            q = self._hits.setdefault(key, deque())
            cutoff = now - self.window
            while q and q[0] < cutoff:
                q.popleft()
            if len(q) >= self.capacity:
                retry_after = max(0.0, self.window - (now - q[0]))
                return False, retry_after
            q.append(now)
            return True, 0.0

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def _client_ip(request: Request) -> str:
    settings = get_settings()
    if settings.trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Apply the sliding window only to /api/* routes."""

    def __init__(self, app: object, limiter: SlidingWindowLimiter | None = None) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        settings = get_settings()
        self.limiter = limiter or SlidingWindowLimiter(
            capacity=settings.rate_limit_per_min,
            window_seconds=float(settings.rate_limit_window_seconds),
        )

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not request.url.path.startswith("/api/"):
            return await call_next(request)
        key = _client_ip(request)
        allowed, retry_after = self.limiter.check(key)
        if not allowed:
            response = JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "detail": "Too many requests; try again later.",
                },
            )
            response.headers["Retry-After"] = str(int(retry_after) + 1)
            return response
        return await call_next(request)
