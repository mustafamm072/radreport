"""
FHIR R4 DiagnosticReport exporter.

Converts a ParsedReport into a FHIR R4-compliant DiagnosticReport resource.
Output is a plain Python dict that can be serialized to JSON for any FHIR server.

Spec reference: https://www.hl7.org/fhir/diagnosticreport.html
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from .report_schema import ParsedReport


# LOINC codes for common radiology modalities
MODALITY_LOINC: dict[str, dict] = {
    "CT":   {"code": "18748-4", "display": "CT Unspecified Body Region"},
    "MRI":  {"code": "18755-9", "display": "MRI Unspecified Body Region"},
    "MR":   {"code": "18755-9", "display": "MRI Unspecified Body Region"},
    "XR":   {"code": "18748-4", "display": "XR Unspecified Body Region"},
    "CR":   {"code": "18748-4", "display": "Computed Radiography"},
    "US":   {"code": "18760-9", "display": "Ultrasound Unspecified Body Region"},
    "NM":   {"code": "18748-4", "display": "Nuclear Medicine Unspecified Body Region"},
    "PET":  {"code": "44136-0", "display": "PET Scan"},
    "PETCT":{"code": "44136-0", "display": "PET-CT"},
    "DX":   {"code": "18748-4", "display": "Digital X-Ray"},
}

DEFAULT_LOINC = {"code": "18748-4", "display": "Diagnostic Imaging Report"}


def _loinc_for_modality(modality: Optional[str]) -> dict:
    if not modality:
        return DEFAULT_LOINC
    return MODALITY_LOINC.get(modality.upper(), DEFAULT_LOINC)


def _build_presented_form(report: ParsedReport) -> list[dict]:
    """Encode the full report text as a FHIR attachment."""
    import base64
    encoded = base64.b64encode(report.raw_text.encode("utf-8")).decode("utf-8")
    return [{
        "contentType": "text/plain",
        "data": encoded,
        "title": "Full Report Text",
    }]


def _build_contained_observations(report: ParsedReport) -> list[dict]:
    """
    Build FHIR Observation resources for each critical finding.
    These are embedded as contained resources in the DiagnosticReport.
    """
    observations = []

    for i, cf in enumerate(report.critical_findings):
        if cf.negated:
            continue  # Don't emit observations for negated findings

        obs_id = f"obs-critical-{i}"
        observations.append({
            "resourceType": "Observation",
            "id": obs_id,
            "status": "preliminary",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                    "code": "imaging",
                    "display": "Imaging",
                }]
            }],
            "code": {
                "text": cf.term,
            },
            "valueString": cf.context,
            "interpretation": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                    "code": "A" if cf.severity == "critical" else "H",
                    "display": "Abnormal" if cf.severity == "critical" else "High",
                }],
                "text": cf.severity,
            }],
            "extension": [{
                "url": "http://example.org/fhir/StructureDefinition/finding-category",
                "valueString": cf.category,
            }],
        })

    return observations


class FHIRExporter:
    """
    Exports a ParsedReport as a FHIR R4 DiagnosticReport resource.

    Usage:
        exporter = FHIRExporter()
        fhir_dict = exporter.export(parsed_report)
        json_str = json.dumps(fhir_dict, indent=2)
    """

    def export(
        self,
        report: ParsedReport,
        patient_id: Optional[str] = None,
        report_id: Optional[str] = None,
        issued_dt: Optional[datetime] = None,
    ) -> dict:
        """
        Convert a ParsedReport to a FHIR R4 DiagnosticReport dict.

        Args:
            report:     ParsedReport from ReportParser (with optional critical findings).
            patient_id: Optional FHIR Patient resource ID reference.
            report_id:  Optional ID for this DiagnosticReport. Auto-generated if omitted.
            issued_dt:  Report issue datetime. Defaults to now (UTC).

        Returns:
            dict representing a valid FHIR R4 DiagnosticReport resource.
        """
        resource_id = report_id or str(uuid.uuid4())
        issued = (issued_dt or datetime.now(timezone.utc)).isoformat()
        loinc = _loinc_for_modality(report.modality)

        contained_obs = _build_contained_observations(report)
        result_refs = [{"reference": f"#{obs['id']}"} for obs in contained_obs]

        # Core DiagnosticReport structure
        resource: dict = {
            "resourceType": "DiagnosticReport",
            "id": resource_id,
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "RAD",
                    "display": "Radiology",
                }]
            }],
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": loinc["code"],
                    "display": loinc["display"],
                }],
                "text": loinc["display"],
            },
            "issued": issued,
            "presentedForm": _build_presented_form(report),
        }

        # Optional patient reference
        if patient_id:
            resource["subject"] = {"reference": f"Patient/{patient_id}"}

        # Impression → conclusion
        if report.impression:
            resource["conclusion"] = report.impression

        # Critical findings as contained Observations
        if contained_obs:
            resource["contained"] = contained_obs
            resource["result"] = result_refs

        # Extension: structured sections
        section_extensions = []
        for section in report.sections:
            section_extensions.append({
                "url": "http://example.org/fhir/StructureDefinition/report-section",
                "extension": [
                    {"url": "name",    "valueString": section.name},
                    {"url": "content", "valueString": section.raw_text},
                ],
            })

        if section_extensions:
            resource["extension"] = section_extensions

        return resource
