"""Watermark detector — read-only structured report.

Reuses the primitives from `engines.cleaner.detect_only` without coupling
mutating logic. Returns a structured `WatermarkReport` that mirrors
`CleaningReport` from `models.py` but is detection-only (no `removed_count`
because nothing is removed at this stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from humanizer.engines.cleaner import detect_only
from humanizer.models import WatermarkFinding


@dataclass
class WatermarkReport:
    zero_width_count: int = 0
    nbsp_count: int = 0
    control_char_count: int = 0
    homoglyph_count: int = 0
    bom_count: int = 0
    non_standard_space_count: int = 0
    findings: list[WatermarkFinding] = field(default_factory=list)

    @property
    def total(self) -> int:
        return (
            self.zero_width_count
            + self.nbsp_count
            + self.control_char_count
            + self.homoglyph_count
            + self.bom_count
            + self.non_standard_space_count
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "zero_width_count": self.zero_width_count,
            "nbsp_count": self.nbsp_count,
            "control_char_count": self.control_char_count,
            "homoglyph_count": self.homoglyph_count,
            "bom_count": self.bom_count,
            "non_standard_space_count": self.non_standard_space_count,
            "total": self.total,
            "findings": [f.model_dump() for f in self.findings],
        }


def detect_watermarks(text: str) -> WatermarkReport:
    findings = detect_only(text)
    report = WatermarkReport(findings=findings)
    for f in findings:
        if f.kind == "zero_width":
            report.zero_width_count += 1
        elif f.kind == "nbsp":
            report.nbsp_count += 1
        elif f.kind == "control_char":
            report.control_char_count += 1
        elif f.kind == "homoglyph":
            report.homoglyph_count += 1
        elif f.kind == "bom":
            report.bom_count += 1
        elif f.kind == "non_standard_space":
            report.non_standard_space_count += 1
    return report
