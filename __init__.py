"""
radreport-parser
~~~~~~~~~~~~~~~~
Parse, structure, and export radiology free-text reports.

Quick start:
    from radreport_parser import ReportParser, CriticalFindingsDetector, FHIRExporter

    parser   = ReportParser()
    detector = CriticalFindingsDetector()
    exporter = FHIRExporter()

    report = parser.parse(raw_text, modality="CT")
    report = detector.detect(report)
    fhir   = exporter.export(report, patient_id="pt-001")
"""

from .report_parser import ReportParser
from .critical_findings import CriticalFindingsDetector
from .fhir_exporter import FHIRExporter
from .report_schema import (
    ParsedReport,
    ReportSection,
    Finding,
    Measurement,
    CriticalFinding,
)

__version__ = "0.1.0"
__all__ = [
    "ReportParser",
    "CriticalFindingsDetector",
    "FHIRExporter",
    "ParsedReport",
    "ReportSection",
    "Finding",
    "Measurement",
    "CriticalFinding",
]
