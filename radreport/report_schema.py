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
class Redaction:
    """A single span of PHI removed from a report during de-identification."""
    category: str        # e.g. "date", "mrn", "name", "phone"
    original: str        # The original text that was redacted
    replacement: str     # The placeholder token substituted in, e.g. "[DATE]"
    start: int           # Start offset in the original text
    end: int             # End offset in the original text (exclusive)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "original": self.original,
            "replacement": self.replacement,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class DeidentificationResult:
    """
    Output of Deidentifier.deidentify().

    `text` is the scrubbed report, safe to store or share. `redactions` is the
    ordered audit trail of every span that was removed, keyed to offsets in the
    ORIGINAL text so the transformation is fully reproducible and reviewable.
    """
    text: str
    redactions: list["Redaction"] = field(default_factory=list)

    @property
    def redaction_count(self) -> int:
        return len(self.redactions)

    def category_counts(self) -> dict[str, int]:
        """Number of redactions per PHI category, useful for audit summaries."""
        counts: dict[str, int] = {}
        for r in self.redactions:
            counts[r.category] = counts.get(r.category, 0) + 1
        return counts

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "redaction_count": self.redaction_count,
            "category_counts": self.category_counts(),
            "redactions": [r.to_dict() for r in self.redactions],
        }


@dataclass
class FindingComparison:
    """
    A single trackable finding compared against a prior study.

    `status` uses the standard radiology interval-change vocabulary:
      "new"       — present now, no match in the prior study
      "increased" — matched, largest dimension grew past the change thresholds
      "decreased" — matched, largest dimension shrank past the change thresholds
      "stable"    — matched, change within thresholds (no meaningful interval change)
      "resolved"  — present in the prior study, no match now

    Measurements are the largest dimension of the finding, normalized to mm.
    `delta_mm` and `percent_change` are current relative to prior (positive =
    growth). They are None for "new"/"resolved" or when a side lacks a
    measurement.
    """
    status: str
    anatomy: Optional[str] = None
    current_text: Optional[str] = None
    prior_text: Optional[str] = None
    current_mm: Optional[float] = None
    prior_mm: Optional[float] = None
    delta_mm: Optional[float] = None
    percent_change: Optional[float] = None
    match_score: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "anatomy": self.anatomy,
            "current_text": self.current_text,
            "prior_text": self.prior_text,
            "current_mm": self.current_mm,
            "prior_mm": self.prior_mm,
            "delta_mm": self.delta_mm,
            "percent_change": self.percent_change,
            "match_score": self.match_score,
        }


@dataclass
class ComparisonResult:
    """
    Output of ReportComparator.compare(). An interval-change summary between a
    current study and a prior one, expressed as a list of FindingComparison
    objects (one per trackable/measurable finding on either side).
    """
    comparisons: list["FindingComparison"] = field(default_factory=list)

    def by_status(self, status: str) -> list["FindingComparison"]:
        return [c for c in self.comparisons if c.status == status]

    def status_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for c in self.comparisons:
            counts[c.status] = counts.get(c.status, 0) + 1
        return counts

    @property
    def has_progression(self) -> bool:
        """True if any finding is new or increased — the clinically worrying cases."""
        return any(c.status in ("new", "increased") for c in self.comparisons)

    def to_dict(self) -> dict:
        return {
            "status_counts": self.status_counts(),
            "has_progression": self.has_progression,
            "comparisons": [c.to_dict() for c in self.comparisons],
        }


@dataclass
class TemplateItemResult:
    """
    The coverage result for a single checklist item of a report template —
    i.e. whether the report actually addressed this anatomic structure or
    evaluation point.

    `matched_keyword` records which of the item's keywords triggered the match,
    so the decision is fully auditable.
    """
    key: str
    label: str
    covered: bool
    required: bool = True
    matched_keyword: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "covered": self.covered,
            "required": self.required,
            "matched_keyword": self.matched_keyword,
        }


@dataclass
class TemplateMatch:
    """
    Output of TemplateMatcher.match(). A completeness assessment of a report
    against a structured report template for its study type.

    Each `TemplateItemResult` records whether an expected anatomic structure /
    evaluation point was addressed. `completeness` is the fraction of *required*
    items that were covered — a rule-based, auditable quality signal for QA
    dashboards and research-cohort validation.
    """
    template_key: str
    template_name: str
    auto_selected: bool
    items: list["TemplateItemResult"] = field(default_factory=list)
    classification_score: Optional[float] = None

    @property
    def covered_items(self) -> list["TemplateItemResult"]:
        return [i for i in self.items if i.covered]

    @property
    def missing_items(self) -> list["TemplateItemResult"]:
        """Required items the report did not address — the completeness gaps."""
        return [i for i in self.items if i.required and not i.covered]

    @property
    def completeness(self) -> float:
        """
        Fraction of required items that were covered, in [0.0, 1.0].
        A template with no required items is trivially complete (1.0).
        """
        required = [i for i in self.items if i.required]
        if not required:
            return 1.0
        covered = sum(1 for i in required if i.covered)
        return round(covered / len(required), 3)

    @property
    def is_complete(self) -> bool:
        return not self.missing_items

    def to_dict(self) -> dict:
        return {
            "template_key": self.template_key,
            "template_name": self.template_name,
            "auto_selected": self.auto_selected,
            "classification_score": self.classification_score,
            "completeness": self.completeness,
            "is_complete": self.is_complete,
            "missing_item_keys": [i.key for i in self.missing_items],
            "items": [i.to_dict() for i in self.items],
        }

    def to_flat_dict(self) -> dict[str, Any]:
        """Flat key/value representation, suitable for merging into a CSV row."""
        return {
            "template_key": self.template_key,
            "template_completeness": self.completeness,
            "template_missing_count": len(self.missing_items),
            "template_missing_items": ";".join(i.key for i in self.missing_items),
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
