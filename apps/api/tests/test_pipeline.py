"""Pipeline orchestrator tests."""

from __future__ import annotations

from humanizer.models import DetectRequest, HumanizeRequest
from humanizer.pipeline import run_detect, run_humanize, _to_verdict


def test_verdict_thresholds() -> None:
    assert _to_verdict(0.0) == "human"
    assert _to_verdict(0.34) == "human"
    assert _to_verdict(0.5) == "mixed"
    assert _to_verdict(0.64) == "mixed"
    assert _to_verdict(0.65) == "ai"
    assert _to_verdict(1.0) == "ai"


def test_run_humanize_en_returns_shape() -> None:
    req = HumanizeRequest(
        text=(
            "Furthermore, the system delves into the realm of robust automation. "
            "Moreover, it leverages a plethora of intricate features. "
            "Additionally, navigating these landscapes is crucial."
        ),
        language="en",
        strength="aggressive",
    )
    resp = run_humanize(req)
    assert resp.language == "en"
    assert resp.strength == "aggressive"
    assert resp.humanized_text
    assert 0.0 <= resp.metrics_before.ai_probability <= 1.0
    assert 0.0 <= resp.metrics_after.ai_probability <= 1.0
    assert resp.latency_ms >= 0.0


def test_run_humanize_he_returns_shape() -> None:
    req = HumanizeRequest(
        text=(
            "יתרה מכך, המערכת משמעותית ומכריעה. בנוסף, היא חיונית וקריטית. "
            "אולם, ניתן לראות כי תפקידה מרכזי במארג זה."
        ),
        language="he",
        strength="medium",
    )
    resp = run_humanize(req)
    assert resp.language == "he"
    assert resp.humanized_text


def test_run_detect_returns_metrics_and_segments() -> None:
    req = DetectRequest(
        text=(
            "Furthermore, the model delves into the intricate realm. "
            "Moreover, it leverages a plethora of robust capabilities. "
            "Additionally, navigating these landscapes is significant. "
            "The framework underscores the importance of automation."
        ),
        language="en",
    )
    resp = run_detect(req)
    assert 0.0 <= resp.ai_probability <= 1.0
    assert resp.verdict in ("human", "mixed", "ai")
    assert resp.metrics.ai_phrase_density > 0
    assert resp.synthid is None
    assert isinstance(resp.highlighted_segments, list)


def test_detect_clean_text_lower_probability_than_ai_text() -> None:
    ai_text = (
        "Furthermore, the model delves into the intricate realm. "
        "Moreover, it leverages a plethora of robust capabilities. "
        "Additionally, navigating these landscapes is significant."
    )
    human_text = (
        "I went to the park yesterday. The dog chased a squirrel up a tree. "
        "We laughed so hard! Then it started raining and we ran home."
    )
    p_ai = run_detect(DetectRequest(text=ai_text, language="en")).ai_probability
    p_human = run_detect(DetectRequest(text=human_text, language="en")).ai_probability
    assert p_ai > p_human


def test_humanize_reduces_or_holds_probability_on_ai_text() -> None:
    text = (
        "Furthermore, the system delves into the realm of robust automation. "
        "Moreover, it leverages a plethora of features. "
        "Additionally, navigating these intricate landscapes is crucial. "
        "The framework underscores the importance of efficiency."
    )
    resp = run_humanize(
        HumanizeRequest(text=text, language="en", strength="aggressive")
    )
    # On clearly AI-style text aggressive humanization should not raise probability.
    assert resp.metrics_after.ai_probability <= resp.metrics_before.ai_probability + 0.05


def test_detect_with_watermarks_reports_findings() -> None:
    text = "Hello\u200B world\u00A0this has hidden marks."
    resp = run_detect(DetectRequest(text=text, language="en"))
    assert len(resp.watermark_findings) >= 2
