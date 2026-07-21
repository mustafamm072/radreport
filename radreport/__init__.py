"""
radreport
~~~~~~~~~
Parse, de-identify, structure, and export radiology free-text reports.

Quick start:
    from radreport import ReportParser, CriticalFindingsDetector, FHIRExporter
    from radreport import RecommendationExtractor, Deidentifier

    parser    = ReportParser()
    detector  = CriticalFindingsDetector()
    extractor = RecommendationExtractor()
    exporter  = FHIRExporter()

    # Optional: strip PHI first so downstream output is safe to share.
    raw_text = Deidentifier().deidentify(raw_text).text

    report = parser.parse(raw_text, modality="CT")
    report = detector.detect(report)
    report = extractor.extract(report)
    fhir   = exporter.export(report, patient_id="pt-001")

    # Flat dict for CSV/pandas:
    row = report.to_flat_dict()
"""

from .report_parser import ReportParser
from .critical_findings import CriticalFindingsDetector
from .recommendation_extractor import RecommendationExtractor
from .fhir_exporter import FHIRExporter
from .deidentifier import Deidentifier, deidentify
from .report_comparator import ReportComparator, compare_reports
from .templates import (
    TemplateMatcher,
    match_template,
    ReportTemplate,
    TemplateItem,
    TEMPLATES,
)
from .report_schema import (
    ParsedReport,
    ReportSection,
    Finding,
    Measurement,
    CriticalFinding,
    FollowUpRecommendation,
    Redaction,
    DeidentificationResult,
    FindingComparison,
    ComparisonResult,
    TemplateItemResult,
    TemplateMatch,
)

__version__ = "0.6.0"
__all__ = [
    "ReportParser",
    "CriticalFindingsDetector",
    "RecommendationExtractor",
    "FHIRExporter",
    "Deidentifier",
    "deidentify",
    "ReportComparator",
    "compare_reports",
    "TemplateMatcher",
    "match_template",
    "ReportTemplate",
    "TemplateItem",
    "TEMPLATES",
    "ParsedReport",
    "ReportSection",
    "Finding",
    "Measurement",
    "CriticalFinding",
    "FollowUpRecommendation",
    "Redaction",
    "DeidentificationResult",
    "FindingComparison",
    "ComparisonResult",
    "TemplateItemResult",
    "TemplateMatch",
    "__version__",
]
