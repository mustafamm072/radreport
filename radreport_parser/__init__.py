"""
radreport-parser
~~~~~~~~~~~~~~~~
Parse, structure, and export radiology free-text reports.

Quick start:
    from radreport_parser import ReportParser, CriticalFindingsDetector, FHIRExporter
    from radreport_parser import RecommendationExtractor

    parser    = ReportParser()
    detector  = CriticalFindingsDetector()
    extractor = RecommendationExtractor()
    exporter  = FHIRExporter()

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
from .report_schema import (
    ParsedReport,
    ReportSection,
    Finding,
    Measurement,
    CriticalFinding,
    FollowUpRecommendation,
)

__version__ = "0.3.0"
__all__ = [
    "ReportParser",
    "CriticalFindingsDetector",
    "RecommendationExtractor",
    "FHIRExporter",
    "ParsedReport",
    "ReportSection",
    "Finding",
    "Measurement",
    "CriticalFinding",
    "FollowUpRecommendation",
    "__version__",
]
