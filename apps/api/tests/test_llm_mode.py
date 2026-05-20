"""LLM mode endpoint + auth gate tests.

Mocks Gemini network calls so no real API quota is consumed.
"""

from __future__ import annotations

import base64
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _basic(user: str, password: str) -> str:
    token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


# ---------------------------------------------------------------------------
# Gate: not configured (no env vars)
# ---------------------------------------------------------------------------


def test_llm_endpoint_503_when_not_configured(client: TestClient) -> None:
    """With no LLM_USER / LLM_PASSWORD env set, /humanize/llm returns 503."""
    from humanizer.settings import get_settings

    settings = get_settings()
    # Default settings have all three empty
    assert not settings.llm_user
    assert not settings.llm_password
    r = client.post(
        "/api/humanize/llm",
        json={"text": "test", "language": "en", "strength": "medium"},
    )
    assert r.status_code == 503
    assert r.json()["detail"] == "llm_mode_not_configured"


# ---------------------------------------------------------------------------
# Gate: configured (patch settings to enable LLM mode)
# ---------------------------------------------------------------------------


@pytest.fixture
def configured(monkeypatch: pytest.MonkeyPatch):
    """Configure LLM mode via env vars + clear the settings cache.

    Because consumers (`auth.py`, `routes.py`) do `from humanizer.settings
    import get_settings`, patching the function reference is insufficient.
    Instead we set env vars and invalidate the cached Settings instance.
    """
    from humanizer import settings as settings_mod

    monkeypatch.setenv("LLM_USER", "test@example.com")
    monkeypatch.setenv("LLM_PASSWORD", "test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    settings_mod._settings = None  # type: ignore[attr-defined]
    yield
    settings_mod._settings = None  # type: ignore[attr-defined]


def test_llm_endpoint_401_on_missing_auth(client: TestClient, configured) -> None:
    r = client.post(
        "/api/humanize/llm",
        json={"text": "test", "language": "en", "strength": "medium"},
    )
    assert r.status_code == 401


def test_llm_endpoint_401_on_wrong_password(client: TestClient, configured) -> None:
    r = client.post(
        "/api/humanize/llm",
        json={"text": "test", "language": "en", "strength": "medium"},
        headers={"Authorization": _basic("test@example.com", "WRONG")},
    )
    assert r.status_code == 401


def test_llm_endpoint_401_on_wrong_user(client: TestClient, configured) -> None:
    r = client.post(
        "/api/humanize/llm",
        json={"text": "test", "language": "en", "strength": "medium"},
        headers={"Authorization": _basic("attacker@evil.com", "test-secret")},
    )
    assert r.status_code == 401


def test_llm_endpoint_502_when_gemini_fails(client: TestClient, configured) -> None:
    """Valid creds + Gemini call fails (network error) → 502."""
    from humanizer.engines import llm_polish

    def _boom(*args, **kwargs):
        raise llm_polish.LLMPolishError("gemini_network_error: boom")

    with patch.object(llm_polish, "polish", side_effect=_boom):
        r = client.post(
            "/api/humanize/llm",
            json={"text": "Hello world.", "language": "en", "strength": "medium"},
            headers={"Authorization": _basic("test@example.com", "test-secret")},
        )
    assert r.status_code == 502
    assert "llm_polish_failed" in r.json()["detail"]


def test_llm_endpoint_200_happy_path(client: TestClient, configured) -> None:
    """Valid creds + mocked Gemini returns text → 200 with full payload."""
    from humanizer.engines import llm_polish

    async def _fake_polish(text, language, strength, api_key):
        return llm_polish.LLMPolishResult(
            text="Polished output from the LLM.",
            model="gemini-3.5-flash",
            prompt_tokens=42,
            output_tokens=17,
        )

    with patch.object(llm_polish, "polish", side_effect=_fake_polish):
        r = client.post(
            "/api/humanize/llm",
            json={
                "text": "The system was designed to leverage AI capabilities.",
                "language": "en",
                "strength": "medium",
            },
            headers={"Authorization": _basic("test@example.com", "test-secret")},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["humanized_text"] == "Polished output from the LLM."
    assert body["llm_model"] == "gemini-3.5-flash"
    assert body["llm_prompt_tokens"] == 42
    assert body["llm_output_tokens"] == 17
    assert "metrics_before" in body
    assert "metrics_after" in body
    assert any(t.startswith("llm_polish:") for t in body["transformations"])


# ---------------------------------------------------------------------------
# Gemini engine unit tests (no network)
# ---------------------------------------------------------------------------


def test_llm_polish_raises_on_empty_api_key() -> None:
    import asyncio

    from humanizer.engines.llm_polish import LLMPolishError, polish

    with pytest.raises(LLMPolishError, match="gemini_api_key_missing"):
        asyncio.run(polish("text", "en", "medium", ""))


def test_llm_polish_payload_includes_strength_temperature() -> None:
    """Internal sanity check that strength → temperature wiring works."""
    from humanizer.engines.llm_polish import _build_payload

    light = _build_payload("hi", "en", "light")
    aggressive = _build_payload("hi", "en", "aggressive")
    assert light["generationConfig"]["temperature"] < aggressive["generationConfig"]["temperature"]


def test_llm_polish_extracts_text_from_candidates() -> None:
    from humanizer.engines.llm_polish import _extract_text

    resp = {
        "candidates": [
            {"content": {"parts": [{"text": "hello "}, {"text": "world"}]}}
        ]
    }
    assert _extract_text(resp) == "hello world"


def test_llm_polish_extract_raises_on_blocked_response() -> None:
    from humanizer.engines.llm_polish import LLMPolishError, _extract_text

    blocked = {"candidates": [], "promptFeedback": {"blockReason": "SAFETY"}}
    with pytest.raises(LLMPolishError, match="blocked: SAFETY"):
        _extract_text(blocked)


# ---------------------------------------------------------------------------
# LLM-first ordering: Python scrubs whatever Gemini brings back in
# ---------------------------------------------------------------------------


def test_llm_output_gets_scrubbed_by_post_pipeline(
    client: TestClient, configured
) -> None:
    """If Gemini returns text containing AI vocabulary and zero-width
    watermark characters, the post-LLM cleaner + lexical engines must
    remove them before the response reaches the user.
    """
    from humanizer.engines import llm_polish

    # Gemini's "polished" output deliberately contains:
    #  - "utilize" + "leverage" + "delve" (AI vocabulary the lexical engine kills)
    #  - U+200B zero-width space (the cleaner strips it)
    dirty = (
        "Companies utilize this approach to leverage their data.\u200B "
        "Teams delve into the details every week."
    )

    async def _fake_polish(text, language, strength, api_key):
        return llm_polish.LLMPolishResult(
            text=dirty,
            model="gemini-3.5-flash",
            prompt_tokens=10,
            output_tokens=20,
        )

    with patch.object(llm_polish, "polish", side_effect=_fake_polish):
        r = client.post(
            "/api/humanize/llm",
            json={
                "text": "Original input sentence about the topic.",
                "language": "en",
                "strength": "aggressive",
            },
            headers={"Authorization": _basic("test@example.com", "test-secret")},
        )

    assert r.status_code == 200, r.text
    body = r.json()
    out = body["humanized_text"]
    # Watermark must be gone.
    assert "\u200B" not in out
    # AI vocabulary must be replaced.
    assert "utilize" not in out.lower()
    assert "leverage" not in out.lower()
    assert "delve" not in out.lower()


def test_llm_pipeline_calls_engines_in_correct_order(
    client: TestClient, configured
) -> None:
    """Verify the call order is:
    cleaner(input) -> LLM -> cleaner -> lexical -> structural -> cleaner.
    """
    from humanizer.engines import cleaner, lexical_en, llm_polish, structural

    calls: list[str] = []

    real_clean = cleaner.clean
    real_lex = lexical_en.humanize_lexical
    real_struct = structural.humanize_structural

    def _rec_clean(text):
        calls.append("cleaner")
        return real_clean(text)

    def _rec_lex(text, strength):
        calls.append("lexical")
        return real_lex(text, strength)

    def _rec_struct(text, language, strength):
        calls.append("structural")
        return real_struct(text, language, strength)

    async def _fake_polish(text, language, strength, api_key):
        calls.append("llm")
        return llm_polish.LLMPolishResult(text=text, model="gemini-3.5-flash")

    with (
        patch.object(cleaner, "clean", side_effect=_rec_clean),
        patch.object(lexical_en, "humanize_lexical", side_effect=_rec_lex),
        patch.object(structural, "humanize_structural", side_effect=_rec_struct),
        patch.object(llm_polish, "polish", side_effect=_fake_polish),
    ):
        r = client.post(
            "/api/humanize/llm",
            json={"text": "Hello world.", "language": "en", "strength": "medium"},
            headers={"Authorization": _basic("test@example.com", "test-secret")},
        )

    assert r.status_code == 200, r.text
    llm_idx = calls.index("llm")
    lex_idx = calls.index("lexical")
    struct_idx = calls.index("structural")
    # LLM happens before lexical and structural.
    assert llm_idx < lex_idx < struct_idx
    # At least one cleaner call before the LLM (input scrub).
    assert "cleaner" in calls[:llm_idx]
    # And at least one cleaner call after the LLM (LLM-output scrub).
    assert "cleaner" in calls[llm_idx + 1 :]
