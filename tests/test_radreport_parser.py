"""
Tests for radreport-parser.
Run with: pytest tests/ -v
"""

import pytest

from radreport_parser import ReportParser, CriticalFindingsDetector, FHIRExporter

# ---------------------------------------------------------------------------
# Sample reports for testing
# ---------------------------------------------------------------------------

CT_CHEST_REPORT = """
INDICATION: Chest pain, rule out pulmonary embolism.

TECHNIQUE: CT pulmonary angiography with IV contrast.

COMPARISON: Chest X-ray from 03/10/2024.

FINDINGS:
Lungs: There is a filling defect in the right main pulmonary artery consistent with pulmonary embolism. No pneumothorax identified. Mild bilateral pleural effusions. The lungs otherwise show no consolidation or mass.

Heart: The heart is normal in size. No pericardial effusion.

Mediastinum: No mediastinal lymphadenopathy. No pneumomediastinum.

Soft tissues: Unremarkable.

IMPRESSION:
1. Pulmonary embolism involving the right main pulmonary artery. Urgent clinical correlation recommended.
2. Bilateral pleural effusions, mild.
3. No pneumothorax.
"""

MRI_BRAIN_REPORT = """
INDICATION: Headache and altered mental status.

TECHNIQUE: MRI brain without and with contrast.

FINDINGS:
Brain: There is a 2.3 x 1.8 cm hyperdense extra-axial collection along the right frontoparietal convexity consistent with acute subdural hematoma. There is associated 5mm midline shift to the left. No hydrocephalus. Sulci are effaced on the right.

Ventricles: The ventricles are normal in size and configuration.

Posterior fossa: Unremarkable.

White matter: No abnormal signal.

IMPRESSION:
Acute right frontoparietal subdural hematoma measuring 2.3 x 1.8 cm with 5mm leftward midline shift. Neurosurgical consultation recommended urgently.
"""

NORMAL_XRAY_REPORT = """
INDICATION: Annual chest X-ray.

TECHNIQUE: PA and lateral views.

FINDINGS:
Lungs: The lungs are clear. No consolidation, effusion, or pneumothorax. No pulmonary nodule identified.

Heart: Normal cardiac silhouette.

Mediastinum: Normal mediastinal contour. No lymphadenopathy.

Bones: No acute osseous abnormality.

IMPRESSION:
Normal chest radiograph. No acute cardiopulmonary process.
"""

ABDOMINAL_CT = """
INDICATION: Abdominal pain, fever.

FINDINGS:
Liver: Normal size and attenuation. No focal hepatic lesion.
Gallbladder: Distended with wall thickening to 6mm and pericholecystic fluid. Findings consistent with acute cholecystitis.
Appendix: Normal appendix identified. No periappendiceal fat stranding.
Bowel: No bowel obstruction. No free air under the diaphragm.
Kidneys: Right kidney measures 11.2 x 5.4 cm. Left kidney 10.8 x 5.1 cm. No hydronephrosis.

IMPRESSION:
Acute cholecystitis. No pneumoperitoneum. No appendicitis.
"""


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

class TestReportParser:

    def setup_method(self):
        self.parser = ReportParser()

    def test_parses_ct_chest_sections(self):
        result = self.parser.parse(CT_CHEST_REPORT, modality="CT")
        section_names = [s.name for s in result.sections]
        assert "indication" in section_names
        assert "findings" in section_names
        assert "impression" in section_names

    def test_modality_stored(self):
        result = self.parser.parse(CT_CHEST_REPORT, modality="CT")
        assert result.modality == "CT"

    def test_impression_extracted(self):
        result = self.parser.parse(CT_CHEST_REPORT)
        assert "pulmonary embolism" in result.impression.lower()

    def test_empty_report_raises(self):
        with pytest.raises(ValueError):
            self.parser.parse("")

    def test_measurement_extraction(self):
        result = self.parser.parse(MRI_BRAIN_REPORT, modality="MRI")
        assert len(result.all_measurements) > 0

    def test_measurement_normalized_to_mm(self):
        result = self.parser.parse(MRI_BRAIN_REPORT, modality="MRI")
        # "2.3 x 1.8 cm" should normalize to [23.0, 18.0] mm
        two_dim = [m for m in result.all_measurements if len(m.dimensions_mm) == 2]
        assert any(abs(m.dimensions_mm[0] - 23.0) < 0.1 for m in two_dim)

    def test_kidney_measurement_mm(self):
        result = self.parser.parse(ABDOMINAL_CT, modality="CT")
        # "11.2 x 5.4 cm" → [112.0, 54.0]
        two_dim = [m for m in result.all_measurements if len(m.dimensions_mm) == 2]
        assert any(abs(m.dimensions_mm[0] - 112.0) < 0.1 for m in two_dim)

    def test_findings_linked_to_anatomy(self):
        result = self.parser.parse(MRI_BRAIN_REPORT, modality="MRI")
        findings_section = result.get_section("findings")
        assert findings_section is not None
        anatomies = [f.anatomy for f in findings_section.findings if f.anatomy]
        assert len(anatomies) > 0

    def test_get_section_case_insensitive(self):
        result = self.parser.parse(CT_CHEST_REPORT)
        assert result.get_section("IMPRESSION") is not None
        assert result.get_section("Impression") is not None

    def test_no_sections_fallback(self):
        bare_text = "Lungs are clear. Heart is normal. No acute findings."
        result = self.parser.parse(bare_text)
        assert len(result.sections) > 0

    def test_to_dict_structure(self):
        result = self.parser.parse(CT_CHEST_REPORT, modality="CT")
        d = result.to_dict()
        assert "sections" in d
        assert "impression" in d
        assert "all_measurements" in d
        assert d["modality"] == "CT"


# ---------------------------------------------------------------------------
# Critical findings detector tests
# ---------------------------------------------------------------------------

class TestCriticalFindingsDetector:

    def setup_method(self):
        self.parser   = ReportParser()
        self.detector = CriticalFindingsDetector()

    def test_detects_pulmonary_embolism(self):
        report = self.parser.parse(CT_CHEST_REPORT, modality="CT")
        report = self.detector.detect(report)
        terms = [cf.term for cf in report.critical_findings]
        assert "pulmonary embolism" in terms

    def test_detects_subdural_hematoma(self):
        report = self.parser.parse(MRI_BRAIN_REPORT, modality="MRI")
        report = self.detector.detect(report)
        terms = [cf.term for cf in report.critical_findings]
        assert "subdural hematoma" in terms or "midline shift" in terms

    def test_negation_no_pneumothorax(self):
        report = self.parser.parse(CT_CHEST_REPORT)
        report = self.detector.detect(report)
        pneumo = [cf for cf in report.critical_findings if cf.term == "pneumothorax"]
        # Pneumothorax appears but should be negated ("No pneumothorax identified")
        assert all(cf.negated for cf in pneumo)

    def test_normal_report_no_active_critical(self):
        report = self.parser.parse(NORMAL_XRAY_REPORT)
        report = self.detector.detect(report)
        active = [cf for cf in report.critical_findings if not cf.negated]
        assert len(active) == 0

    def test_severity_ordering(self):
        report = self.parser.parse(CT_CHEST_REPORT)
        report = self.detector.detect(report)
        active = [cf for cf in report.critical_findings if not cf.negated]
        # Critical findings should come before urgent and significant
        severities = [cf.severity for cf in active]
        seen_non_critical = False
        for s in severities:
            if s != "critical":
                seen_non_critical = True
            if seen_non_critical:
                assert s != "critical", "Critical should appear before non-critical"

    def test_context_populated(self):
        report = self.parser.parse(MRI_BRAIN_REPORT)
        report = self.detector.detect(report)
        for cf in report.critical_findings:
            assert len(cf.context) > 0

    def test_supported_terms_list(self):
        terms = self.detector.supported_terms
        assert "pulmonary embolism" in terms
        assert "aortic dissection" in terms
        assert len(terms) > 20


# ---------------------------------------------------------------------------
# FHIR exporter tests
# ---------------------------------------------------------------------------

class TestFHIRExporter:

    def setup_method(self):
        self.parser   = ReportParser()
        self.detector = CriticalFindingsDetector()
        self.exporter = FHIRExporter()

    def _full_pipeline(self, text, modality=None):
        report = self.parser.parse(text, modality=modality)
        report = self.detector.detect(report)
        return self.exporter.export(report, patient_id="pt-test-001")

    def test_resource_type(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT, "CT")
        assert fhir["resourceType"] == "DiagnosticReport"

    def test_status_final(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT)
        assert fhir["status"] == "final"

    def test_patient_reference(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT)
        assert fhir["subject"]["reference"] == "Patient/pt-test-001"

    def test_loinc_code_present(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT, "CT")
        coding = fhir["code"]["coding"][0]
        assert coding["system"] == "http://loinc.org"
        assert coding["code"] is not None

    def test_conclusion_matches_impression(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT)
        assert "pulmonary embolism" in fhir["conclusion"].lower()

    def test_presented_form_base64(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT)
        assert len(fhir["presentedForm"]) > 0
        import base64
        decoded = base64.b64decode(fhir["presentedForm"][0]["data"]).decode("utf-8")
        assert "pulmonary embolism" in decoded.lower()

    def test_critical_findings_as_contained_obs(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT, "CT")
        if "contained" in fhir:
            for obs in fhir["contained"]:
                assert obs["resourceType"] == "Observation"

    def test_no_patient_id_omits_subject(self):
        report = self.parser.parse(NORMAL_XRAY_REPORT)
        report = self.detector.detect(report)
        fhir = self.exporter.export(report)
        assert "subject" not in fhir

    def test_normal_report_no_contained(self):
        report = self.parser.parse(NORMAL_XRAY_REPORT)
        report = self.detector.detect(report)
        fhir = self.exporter.export(report)
        # Normal report → no active critical findings → no contained observations
        contained = fhir.get("contained", [])
        assert len(contained) == 0

    def test_section_extensions_present(self):
        fhir = self._full_pipeline(CT_CHEST_REPORT)
        assert "extension" in fhir
        section_exts = [e for e in fhir["extension"]
                        if "report-section" in e.get("url", "")]
        assert len(section_exts) > 0
