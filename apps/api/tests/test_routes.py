"""Integration tests for /api/humanize and /api/detect."""

from __future__ import annotations

from fastapi.testclient import TestClient

from humanizer.settings import get_settings
from main import create_app


def _client() -> TestClient:
    return TestClient(create_app())


def test_humanize_en_returns_200_with_shape() -> None:
    client = _client()
    r = client.post(
        "/api/humanize",
        json={
            "text": (
                "Furthermore, the system delves into the realm of robust "
                "automation. Moreover, it leverages a plethora of features."
            ),
            "language": "en",
            "strength": "medium",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "humanized_text" in body
    assert "metrics_before" in body and "metrics_after" in body
    assert body["language"] == "en"


def test_humanize_he_returns_200() -> None:
    client = _client()
    r = client.post(
        "/api/humanize",
        json={
            "text": "יתרה מכך, המערכת משמעותית ומכריעה. בנוסף, היא חיונית.",
            "language": "he",
            "strength": "light",
        },
    )
    assert r.status_code == 200
    assert r.json()["language"] == "he"


def test_humanize_rejects_oversize_payload() -> None:
    client = _client()
    cap = get_settings().max_text_length
    oversized = "a " * (cap // 2 + 1000)  # > cap chars but valid
    r = client.post(
        "/api/humanize",
        json={"text": oversized, "language": "en", "strength": "light"},
    )
    assert r.status_code == 413


def test_humanize_422_on_invalid_strength() -> None:
    client = _client()
    r = client.post(
        "/api/humanize",
        json={"text": "hello", "language": "en", "strength": "extreme"},
    )
    assert r.status_code == 422


def test_detect_en_returns_metrics_shape() -> None:
    client = _client()
    r = client.post(
        "/api/detect",
        json={
            "text": (
                "Furthermore, the model delves into the intricate realm. "
                "Moreover, it leverages robust capabilities significantly."
            ),
            "language": "en",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert 0.0 <= body["ai_probability"] <= 1.0
    assert body["verdict"] in ("human", "mixed", "ai")
    assert "perplexity_proxy" in body["metrics"]
    assert isinstance(body["highlighted_segments"], list)


def test_detect_he_returns_200() -> None:
    client = _client()
    r = client.post(
        "/api/detect",
        json={"text": "המוצר עובד היטב והוא איכותי.", "language": "he"},
    )
    assert r.status_code == 200


def test_detect_422_on_empty_text() -> None:
    client = _client()
    r = client.post("/api/detect", json={"text": "   ", "language": "en"})
    assert r.status_code == 422
