"""SynthID watermark detector via Hugging Face Transformers (lazy-loaded).

This module is intentionally tolerant of three states:

  1. ``ENABLE_SYNTHID=false`` (default) → returns ``SynthIDResult(enabled=False, available=False)``.
  2. ``ENABLE_SYNTHID=true`` but transformers / model not available → returns
     ``SynthIDResult(enabled=True, available=False, detail=...)`` with the reason logged.
  3. Fully operational → returns a real score in ``[0, 1]``.

The detector is imported on demand so that container start-up does not pay
the multi-GB model-download cost unless the operator opts in.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from humanizer.models import SynthIDResult
from humanizer.settings import get_settings

_logger = logging.getLogger(__name__)

# Cached references so we don't re-import / re-instantiate per request.
_detector: Any | None = None
_loader: Callable[[str], Any] | None = None


@dataclass(frozen=True)
class _LoadOutcome:
    detector: Any | None
    reason: str | None


def _try_load(model_name: str) -> _LoadOutcome:
    """Attempt to import transformers + load a SynthID detector.

    Kept private and isolated so tests can monkeypatch a single seam.
    """
    if _loader is not None:
        try:
            return _LoadOutcome(detector=_loader(model_name), reason=None)
        except Exception as exc:  # noqa: BLE001
            return _LoadOutcome(detector=None, reason=f"loader_error:{exc}")

    try:
        import transformers
    except ImportError:
        return _LoadOutcome(
            detector=None,
            reason="transformers_not_installed",
        )

    # The real production class lives under transformers.generation; importing it
    # lazily so unit tests never need the dependency.
    SynthIDTextWatermarkDetector = getattr(
        transformers, "SynthIDTextWatermarkDetector", None
    )
    if SynthIDTextWatermarkDetector is None:
        return _LoadOutcome(
            detector=None,
            reason="synthid_detector_class_missing_from_transformers",
        )

    try:
        detector = SynthIDTextWatermarkDetector.from_pretrained(model_name)
    except Exception as exc:  # noqa: BLE001
        return _LoadOutcome(detector=None, reason=f"model_load_failed:{exc}")

    return _LoadOutcome(detector=detector, reason=None)


def detect_synthid(text: str, model_name: str | None = None) -> SynthIDResult:
    """Detect SynthID watermark presence.

    Returns ``SynthIDResult(enabled=False, available=False)`` when feature flag is
    off. Otherwise returns a populated result; ``available=False`` indicates the
    backend could not be loaded for an operational reason.
    """
    settings = get_settings()
    if not settings.enable_synthid:
        return SynthIDResult(
            enabled=False,
            available=False,
            score=None,
            detail="ENABLE_SYNTHID=false",
        )

    global _detector
    if _detector is None:
        outcome = _try_load(model_name or settings.synthid_model)
        if outcome.detector is None:
            _logger.warning("synthid_unavailable reason=%s", outcome.reason)
            return SynthIDResult(
                enabled=True,
                available=False,
                score=None,
                detail=outcome.reason,
            )
        _detector = outcome.detector

    try:
        raw = _detector(text)
        score = _coerce_score(raw)
    except Exception as exc:  # noqa: BLE001
        _logger.exception("synthid_runtime_error")
        return SynthIDResult(
            enabled=True,
            available=False,
            score=None,
            detail=f"runtime_error:{exc}",
        )

    return SynthIDResult(
        enabled=True,
        available=True,
        score=score,
        detail=None,
    )


def _coerce_score(raw: Any) -> float:
    """Normalize whatever the detector returns into ``[0, 1]``."""
    if isinstance(raw, (int, float)):
        return max(0.0, min(1.0, float(raw)))
    if isinstance(raw, dict) and "score" in raw:
        return max(0.0, min(1.0, float(raw["score"])))
    # Some HF detectors return a tensor with `.item()`.
    item = getattr(raw, "item", None)
    if callable(item):
        return max(0.0, min(1.0, float(item())))
    raise TypeError(f"unsupported synthid return type: {type(raw).__name__}")


def _set_loader_for_tests(loader: Callable[[str], Any] | None) -> None:
    """Test seam — install a fake loader and reset the cached detector."""
    global _loader, _detector
    _loader = loader
    _detector = None
