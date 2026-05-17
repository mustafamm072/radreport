"""
Data schemas for parsed radiology reports.
All output from the library uses these dataclasses.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Measurement:
    """A normalized measurement extracted from report text."""
    raw: str                        # Original string e.g. "1.2 x 0.8 cm"
    dimensions_mm: list[float]      # Normalized to millimeters
    unit_original: str              # Original unit: "cm", "mm", "in"

    @property
    def is_single(self) -> bool:
        return len(self.dimensions_mm) == 1

    @property
    def largest_dimension_mm(self) -> float:
        return max(self.dimensions_mm)

    def to_dict(self) -> dict:
        return {
            "raw": self.raw,
            "dimensions_mm": self.dimensions_mm,
            "unit_original": self.unit_original,
            "largest_dimension_mm": self.largest_dimension_mm,
        }


@dataclass
class Finding:
    """A single finding sentence, optionally linked to anatomy."""
    text: str
    anatomy: Optional[str] = None
    measurements: list[Measurement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "anatomy": self.anatomy,
            "measurements": [m.to_dict() for m in self.measurements],
        }


@dataclass
class ReportSection:
    """A labeled section of a radiology report."""
    name: str                               # e.g. "findings", "impression"
    raw_text: str                           # Raw section content
    findings: list[Finding] = field(default_factory=list)
    measurements: list[Measurement] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "raw_text": self.raw_text,
            "findings": [f.to_dict() for f in self.findings],
            "measurements": [m.to_dict() for m in self.measurements],
        }


@dataclass
class CriticalFinding:
    """A flagged critical / urgent finding."""
    term: str               # The keyword that triggered the flag
    category: str           # e.g. "vascular", "pulmonary", "neuro"
    severity: str           # "critical" | "urgent" | "significant"
    context: str            # Surrounding sentence for review
    negated: bool = False   # True if finding appears to be negated

    def to_dict(self) -> dict:
        return {
            "term": self.term,
            "category": self.category,
            "severity": self.severity,
            "context": self.context,
            "negated": self.negated,
        }


@dataclass
class ParsedReport:
    """
    Top-level output of ReportParser.parse().
    Contains all structured data extracted from a radiology report.
    """
    raw_text: str
    sections: list[ReportSection]
    impression: str
    findings_text: str
    all_measurements: list[Measurement]
    modality: Optional[str] = None
    critical_findings: list[CriticalFinding] = field(default_factory=list)

    def get_section(self, name: str) -> Optional[ReportSection]:
        """Retrieve a section by name (case-insensitive)."""
        for s in self.sections:
            if s.name.lower() == name.lower():
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "modality": self.modality,
            "sections": [s.to_dict() for s in self.sections],
            "impression": self.impression,
            "findings_text": self.findings_text,
            "all_measurements": [m.to_dict() for m in self.all_measurements],
            "critical_findings": [c.to_dict() for c in self.critical_findings],
        }
