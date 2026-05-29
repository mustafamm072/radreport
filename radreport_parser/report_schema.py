"""
Data schemas for parsed radiology reports.
All output from the library uses these dataclasses.
"""

from dataclasses import dataclass, field
from typing import Optional, Any


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
class FollowUpRecommendation:
    """A structured follow-up imaging recommendation extracted from the report."""
    text: str                          # Original sentence
    interval: Optional[str] = None    # "6 months", "1 year", "annual", "short-term"
    modality: Optional[str] = None    # "CT", "MRI", "US", "XR", "PET", "NM", "mammography"
    urgency: str = "routine"          # "routine" | "urgent"

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "interval": self.interval,
            "modality": self.modality,
            "urgency": self.urgency,
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
    recommendations: list[FollowUpRecommendation] = field(default_factory=list)

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
            "recommendations": [r.to_dict() for r in self.recommendations],
        }

    def to_flat_dict(self) -> dict[str, Any]:
        """
        Flat key/value representation — one row per report, suitable for CSV.

        Fields:
          modality, impression, section_count, measurement_count,
          largest_measurement_mm, critical_finding_count, urgent_finding_count,
          has_active_critical, recommendation_count,
          follow_up_interval, follow_up_modality, follow_up_urgency
        """
        active = [cf for cf in self.critical_findings if not cf.negated]
        first_rec = self.recommendations[0] if self.recommendations else None
        largest = max(
            (m.largest_dimension_mm for m in self.all_measurements),
            default=None,
        )
        return {
            "modality": self.modality or "",
            "impression": self.impression,
            "section_count": len(self.sections),
            "measurement_count": len(self.all_measurements),
            "largest_measurement_mm": largest,
            "critical_finding_count": sum(1 for cf in active if cf.severity == "critical"),
            "urgent_finding_count": sum(1 for cf in active if cf.severity == "urgent"),
            "has_active_critical": any(cf.severity == "critical" for cf in active),
            "recommendation_count": len(self.recommendations),
            "follow_up_interval": first_rec.interval if first_rec else None,
            "follow_up_modality": first_rec.modality if first_rec else None,
            "follow_up_urgency": first_rec.urgency if first_rec else None,
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to a JSON string. Shorthand for json.dumps(report.to_dict())."""
        import json
        return json.dumps(self.to_dict(), indent=indent)
