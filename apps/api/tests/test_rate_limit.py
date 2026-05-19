"""Rate limiter tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from humanizer.rate_limit import SlidingWindowLimiter
from humanizer.settings import get_settings
from main import create_app


def test_limiter_allows_under_capacity() -> None:
    lim = SlidingWindowLimiter(capacity=3, window_seconds=60)
    now = 100.0
    assert lim.check("a", now)[0] is True
    assert lim.check("a", now + 0.1)[0] is True
    assert lim.check("a", now + 0.2)[0] is True


def test_limiter_blocks_over_capacity() -> None:
    lim = SlidingWindowLimiter(capacity=2, window_seconds=60)
    now = 100.0
    assert lim.check("a", now)[0] is True
    assert lim.check("a", now)[0] is True
    allowed, retry = lim.check("a", now)
    assert allowed is False
    assert retry > 0


def test_limiter_window_slides_open() -> None:
    lim = SlidingWindowLimiter(capacity=1, window_seconds=10)
    assert lim.check("a", 100.0)[0] is True
    assert lim.check("a", 105.0)[0] is False
    assert lim.check("a", 111.0)[0] is True  # window has passed


def test_limiter_isolates_keys() -> None:
    lim = SlidingWindowLimiter(capacity=1, window_seconds=60)
    assert lim.check("a", 100.0)[0] is True
    assert lim.check("b", 100.0)[0] is True
    assert lim.check("a", 100.0)[0] is False


def test_middleware_returns_429_after_capacity() -> None:
    s = get_settings()
    original = s.rate_limit_per_min
    s.rate_limit_per_min = 2
    try:
        client = TestClient(create_app())
        payload = {"text": "hello world", "language": "en"}
        r1 = client.post("/api/detect", json=payload)
        r2 = client.post("/api/detect", json=payload)
        r3 = client.post("/api/detect", json=payload)
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429
        assert "Retry-After" in r3.headers
    finally:
        s.rate_limit_per_min = original


def test_health_route_not_rate_limited() -> None:
    s = get_settings()
    original = s.rate_limit_per_min
    s.rate_limit_per_min = 1
    try:
        client = TestClient(create_app())
        for _ in range(5):
            r = client.get("/health")
            assert r.status_code == 200
    finally:
        s.rate_limit_per_min = original
