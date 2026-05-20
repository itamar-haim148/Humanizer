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
