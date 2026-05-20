"""SynthID detector tests using a fake loader (no real model download)."""

from __future__ import annotations

import pytest

from humanizer.engines import detector_synthid as ds
from humanizer.settings import get_settings


@pytest.fixture(autouse=True)
def _reset_state() -> None:
    """Ensure each test starts from a clean cache + default settings."""
    ds._set_loader_for_tests(None)
    s = get_settings()
    original = s.enable_synthid
    yield
    s.enable_synthid = original
    ds._set_loader_for_tests(None)


def test_disabled_by_default_returns_disabled_result() -> None:
    s = get_settings()
    s.enable_synthid = False
    res = ds.detect_synthid("hello")
    assert res.enabled is False
    assert res.available is False
    assert res.score is None


def test_enabled_with_fake_loader_returns_score() -> None:
    s = get_settings()
    s.enable_synthid = True

    class FakeDetector:
        def __call__(self, text: str) -> float:
            return 0.73

    ds._set_loader_for_tests(lambda _model: FakeDetector())
    res = ds.detect_synthid("some text")
    assert res.enabled is True
    assert res.available is True
    assert res.score == pytest.approx(0.73)


def test_enabled_loader_failure_marks_unavailable() -> None:
    s = get_settings()
    s.enable_synthid = True

    def bad_loader(_model: str) -> object:
        raise RuntimeError("disk full")

    ds._set_loader_for_tests(bad_loader)
    res = ds.detect_synthid("text")
    assert res.enabled is True
    assert res.available is False
    assert res.detail is not None and "loader_error" in res.detail


def test_score_dict_return_coerced() -> None:
    s = get_settings()
    s.enable_synthid = True

    class DictDetector:
        def __call__(self, _text: str) -> dict[str, float]:
            return {"score": 0.42}

    ds._set_loader_for_tests(lambda _m: DictDetector())
    res = ds.detect_synthid("text")
    assert res.score == pytest.approx(0.42)


def test_score_clamped_to_unit_interval() -> None:
    s = get_settings()
    s.enable_synthid = True

    ds._set_loader_for_tests(lambda _m: (lambda _t: 1.5))
    res = ds.detect_synthid("text")
    assert res.score == 1.0


# ---------------------------------------------------------------------------
# G-value statistical proxy (no ML deps)
# ---------------------------------------------------------------------------


def test_g_value_deterministic_and_in_unit_interval() -> None:
    a = ds._g_value("foo", "bar")
    b = ds._g_value("foo", "bar")
    assert a == b
    assert 0.0 <= a < 1.0
    # Different inputs yield different outputs.
    assert ds._g_value("foo", "baz") != a


def test_g_value_proxy_short_text_returns_none() -> None:
    # Need at least 4 tokens for a meaningful bigram sample.
    assert ds.g_value_proxy_score("only three words") is None  # 3 tokens
    assert ds.g_value_proxy_score("two only") is None  # 2 tokens


def test_g_value_proxy_returns_unit_score_on_real_text() -> None:
    score = ds.g_value_proxy_score(
        "The quick brown fox jumps over the lazy dog every morning at dawn."
    )
    assert score is not None
    assert 0.0 <= score <= 1.0


def test_loader_failure_with_long_text_falls_back_to_proxy() -> None:
    """When ENABLE_SYNTHID=true and loader fails, the proxy score fills in."""
    s = get_settings()
    s.enable_synthid = True

    def bad_loader(_model: str) -> object:
        raise RuntimeError("disk full")

    ds._set_loader_for_tests(bad_loader)
    res = ds.detect_synthid(
        "The quick brown fox jumps over the lazy dog every morning at dawn."
    )
    assert res.enabled is True
    assert res.available is False
    assert res.score is not None
    assert res.detail is not None and res.detail.startswith("g_value_proxy:")
