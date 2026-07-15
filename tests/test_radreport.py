"""
Tests for radreport.
Run with: pytest tests/ -v
"""

import pytest

from radreport import (
    ReportParser, CriticalFindingsDetector, FHIRExporter, RecommendationExtractor,
    Deidentifier, deidentify, ReportComparator, compare_reports,
)

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

    def test_negated_mention_does_not_suppress_real_finding(self):
        # A negated mention appearing BEFORE a real one must not suppress the
        # real (active) finding — otherwise a true critical alert is dropped.
        text = (
            "FINDINGS:\n"
            "No pneumothorax at the right apex. "
            "A large pneumothorax is present at the left base."
        )
        report = self.parser.parse(text)
        report = self.detector.detect(report)
        pneumo = [cf for cf in report.critical_findings if cf.term == "pneumothorax"]
        assert len(pneumo) == 1
        assert pneumo[0].negated is False
        assert "left base" in pneumo[0].context

    def test_all_negated_reports_as_negated(self):
        # If every mention is negated, the finding stays negated.
        text = (
            "FINDINGS:\n"
            "No pneumothorax on the right. No pneumothorax on the left."
        )
        report = self.parser.parse(text)
        report = self.detector.detect(report)
        pneumo = [cf for cf in report.critical_findings if cf.term == "pneumothorax"]
        assert len(pneumo) == 1
        assert pneumo[0].negated is True

    def test_negation_does_not_cross_sentence_boundary(self):
        # A negation in a previous sentence must not negate a finding in the
        # current sentence, even when within the character window.
        text = (
            "FINDINGS:\n"
            "No acute hemorrhage. Large subdural hematoma is present."
        )
        report = self.parser.parse(text)
        report = self.detector.detect(report)
        sdh = [cf for cf in report.critical_findings if cf.term == "subdural hematoma"]
        assert len(sdh) == 1
        assert sdh[0].negated is False


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


# ---------------------------------------------------------------------------
# parse_batch tests
# ---------------------------------------------------------------------------

class TestParseBatch:

    def setup_method(self):
        self.parser = ReportParser()

    def test_batch_returns_list(self):
        results = self.parser.parse_batch([CT_CHEST_REPORT, MRI_BRAIN_REPORT])
        assert len(results) == 2

    def test_batch_all_parsed(self):
        results = self.parser.parse_batch([CT_CHEST_REPORT, NORMAL_XRAY_REPORT], modality="CT")
        assert all(r is not None for r in results)
        assert all(r.modality == "CT" for r in results)

    def test_batch_empty_input_returns_none(self):
        results = self.parser.parse_batch(["", CT_CHEST_REPORT])
        assert results[0] is None
        assert results[1] is not None

    def test_batch_empty_list(self):
        results = self.parser.parse_batch([])
        assert results == []


# ---------------------------------------------------------------------------
# to_json tests
# ---------------------------------------------------------------------------

class TestToJson:

    def setup_method(self):
        self.parser = ReportParser()

    def test_to_json_is_valid_json(self):
        import json
        report = self.parser.parse(CT_CHEST_REPORT, modality="CT")
        s = report.to_json()
        parsed = json.loads(s)
        assert parsed["modality"] == "CT"

    def test_to_json_contains_sections(self):
        import json
        report = self.parser.parse(MRI_BRAIN_REPORT)
        d = json.loads(report.to_json())
        assert "sections" in d
        assert len(d["sections"]) > 0

    def test_to_json_roundtrip_measurements(self):
        import json
        report = self.parser.parse(MRI_BRAIN_REPORT)
        d = json.loads(report.to_json())
        assert len(d["all_measurements"]) > 0


# ---------------------------------------------------------------------------
# pe abbreviation bug regression
# ---------------------------------------------------------------------------

class TestPEAbbreviationDetection:

    def setup_method(self):
        self.parser = ReportParser()
        self.detector = CriticalFindingsDetector()

    def test_pe_abbreviation_detected(self):
        text = "IMPRESSION: PE in the right main pulmonary artery."
        report = self.parser.parse(text)
        report = self.detector.detect(report)
        terms = [cf.term for cf in report.critical_findings]
        assert "pe" in terms or "pulmonary embolism" in terms

    def test_pe_abbreviation_end_of_sentence(self):
        text = "IMPRESSION: Findings consistent with PE."
        report = self.parser.parse(text)
        report = self.detector.detect(report)
        active = [cf for cf in report.critical_findings if not cf.negated]
        assert any(cf.term in ("pe", "pulmonary embolism") for cf in active)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:

    def setup_method(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def _write_report(self, name, text):
        from pathlib import Path
        p = Path(self.tmp) / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_cli_parses_single_file(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f = self._write_report("report.txt", CT_CHEST_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f])
        result = json.loads(buf.getvalue())
        assert "sections" in result
        assert result["source_file"] == "report.txt"

    def test_cli_fhir_flag(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f = self._write_report("report.txt", CT_CHEST_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f, "--fhir", "--patient-id", "pt-99", "--modality", "CT"])
        result = json.loads(buf.getvalue())
        assert result["resourceType"] == "DiagnosticReport"
        assert result["subject"]["reference"] == "Patient/pt-99"

    def test_cli_batch_returns_list(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f1 = self._write_report("r1.txt", CT_CHEST_REPORT)
        f2 = self._write_report("r2.txt", NORMAL_XRAY_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f1, f2])
        result = json.loads(buf.getvalue())
        assert isinstance(result, list)
        assert len(result) == 2

    def test_cli_missing_file_exits(self):
        from radreport.cli import main
        with pytest.raises(SystemExit):
            main(["/nonexistent/path/report.txt"])

    def test_cli_output_file(self):
        import json
        from pathlib import Path
        from io import StringIO
        from contextlib import redirect_stdout, redirect_stderr
        from radreport.cli import main

        f = self._write_report("report.txt", NORMAL_XRAY_REPORT)
        out = str(Path(self.tmp) / "out.json")
        buf = StringIO()
        with redirect_stdout(buf), redirect_stderr(StringIO()):
            main([f, "-o", out])
        assert buf.getvalue() == ""
        result = json.loads(Path(out).read_text())
        assert "sections" in result

    def test_cli_recommend_flag(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f = self._write_report("report.txt", CT_CHEST_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f, "--recommend"])
        result = json.loads(buf.getvalue())
        assert "recommendations" in result

    def test_cli_csv_format_single_file(self):
        import csv
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f = self._write_report("report.txt", CT_CHEST_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f, "--critical", "--recommend", "--format", "csv"])
        rows = list(csv.DictReader(buf.getvalue().splitlines()))
        assert len(rows) == 1
        assert rows[0]["source_file"] == "report.txt"
        assert "modality" in rows[0]
        assert "largest_measurement_mm" in rows[0]
        assert "recommendation_count" in rows[0]

    def test_cli_csv_format_batch(self):
        import csv
        from io import StringIO
        from contextlib import redirect_stdout
        from radreport.cli import main

        f1 = self._write_report("r1.txt", CT_CHEST_REPORT)
        f2 = self._write_report("r2.txt", MRI_BRAIN_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f1, f2, "--format", "csv"])
        rows = list(csv.DictReader(buf.getvalue().splitlines()))
        assert len(rows) == 2
        filenames = {r["source_file"] for r in rows}
        assert "r1.txt" in filenames
        assert "r2.txt" in filenames

    def test_cli_csv_fhir_conflict(self):
        from radreport.cli import main
        with pytest.raises(SystemExit):
            main(["somefile.txt", "--fhir", "--format", "csv"])


# ---------------------------------------------------------------------------
# Recommendation extractor tests
# ---------------------------------------------------------------------------

class TestRecommendationExtractor:

    def setup_method(self):
        self.parser    = ReportParser()
        self.extractor = RecommendationExtractor()

    def _parse_and_extract(self, text, modality=None):
        report = self.parser.parse(text, modality=modality)
        return self.extractor.extract(report)

    def test_interval_months(self):
        text = "IMPRESSION: Pulmonary nodule. Follow-up CT in 6 months is recommended."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].interval == "6 months"
        assert report.recommendations[0].modality == "CT"

    def test_interval_year(self):
        text = "RECOMMENDATION: Annual CT surveillance recommended."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) >= 1
        assert report.recommendations[0].interval == "annual"

    def test_modality_mri(self):
        text = "IMPRESSION: Consider repeat MRI in 3 months for further evaluation."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].modality == "MRI"
        assert report.recommendations[0].interval == "3 months"

    def test_modality_ultrasound(self):
        text = "RECOMMENDATION: 6-month follow-up ultrasound recommended."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].modality == "US"

    def test_negation_no_follow_up(self):
        text = "IMPRESSION: No follow-up imaging required. Normal study."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 0

    def test_negation_not_indicated(self):
        text = "RECOMMENDATION: Repeat imaging not indicated at this time."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 0

    def test_urgency_urgent(self):
        text = "IMPRESSION: Urgent follow-up CT recommended given rapid growth."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].urgency == "urgent"

    def test_urgency_default_routine(self):
        text = "IMPRESSION: 1-year follow-up CT recommended."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].urgency == "routine"

    def test_no_modality_still_extracted(self):
        text = "IMPRESSION: Follow-up in 3 months is advised."
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1
        assert report.recommendations[0].interval == "3 months"
        assert report.recommendations[0].modality is None

    def test_no_recommendations_on_normal_report(self):
        report = self._parse_and_extract(NORMAL_XRAY_REPORT)
        assert len(report.recommendations) == 0

    def test_recommendations_in_to_dict(self):
        text = "RECOMMENDATION: 6-month follow-up CT recommended."
        report = self._parse_and_extract(text)
        d = report.to_dict()
        assert "recommendations" in d
        assert len(d["recommendations"]) == 1
        rec = d["recommendations"][0]
        assert rec["interval"] == "6 months"
        assert rec["modality"] == "CT"

    def test_deduplication(self):
        # Same sentence in both impression and recommendation sections
        text = (
            "IMPRESSION: 6-month follow-up CT recommended.\n"
            "RECOMMENDATION: 6-month follow-up CT recommended."
        )
        report = self._parse_and_extract(text)
        assert len(report.recommendations) == 1


# ---------------------------------------------------------------------------
# to_flat_dict tests
# ---------------------------------------------------------------------------

class TestToFlatDict:

    def setup_method(self):
        self.parser    = ReportParser()
        self.detector  = CriticalFindingsDetector()
        self.extractor = RecommendationExtractor()

    def _full_parse(self, text, modality=None):
        report = self.parser.parse(text, modality=modality)
        report = self.detector.detect(report)
        return self.extractor.extract(report)

    def test_flat_dict_has_expected_keys(self):
        report = self._full_parse(CT_CHEST_REPORT, "CT")
        flat = report.to_flat_dict()
        expected = {
            "modality", "impression", "section_count", "measurement_count",
            "largest_measurement_mm", "critical_finding_count", "urgent_finding_count",
            "has_active_critical", "recommendation_count",
            "follow_up_interval", "follow_up_modality", "follow_up_urgency",
        }
        assert expected == set(flat.keys())

    def test_flat_dict_modality(self):
        report = self._full_parse(CT_CHEST_REPORT, "CT")
        assert report.to_flat_dict()["modality"] == "CT"

    def test_flat_dict_measurements(self):
        report = self._full_parse(MRI_BRAIN_REPORT, "MRI")
        flat = report.to_flat_dict()
        assert flat["measurement_count"] > 0
        assert flat["largest_measurement_mm"] is not None
        assert flat["largest_measurement_mm"] > 0

    def test_flat_dict_critical_flags(self):
        report = self._full_parse(CT_CHEST_REPORT, "CT")
        flat = report.to_flat_dict()
        assert flat["critical_finding_count"] >= 1
        assert flat["has_active_critical"] is True

    def test_flat_dict_normal_report_zeros(self):
        report = self._full_parse(NORMAL_XRAY_REPORT)
        flat = report.to_flat_dict()
        assert flat["critical_finding_count"] == 0
        assert flat["has_active_critical"] is False
        assert flat["recommendation_count"] == 0

    def test_flat_dict_no_measurements_is_none(self):
        text = "IMPRESSION: Normal study. No acute findings."
        report = self._full_parse(text)
        flat = report.to_flat_dict()
        assert flat["largest_measurement_mm"] is None
        assert flat["measurement_count"] == 0

    def test_flat_dict_recommendation_fields(self):
        text = "IMPRESSION: 6-month follow-up CT recommended for nodule surveillance."
        report = self._full_parse(text)
        flat = report.to_flat_dict()
        assert flat["recommendation_count"] == 1
        assert flat["follow_up_interval"] == "6 months"
        assert flat["follow_up_modality"] == "CT"
        assert flat["follow_up_urgency"] == "routine"

    def test_flat_dict_no_recommendation_fields_are_none(self):
        report = self._full_parse(NORMAL_XRAY_REPORT)
        flat = report.to_flat_dict()
        assert flat["follow_up_interval"] is None
        assert flat["follow_up_modality"] is None
        assert flat["follow_up_urgency"] is None


# ---------------------------------------------------------------------------
# De-identification tests
# ---------------------------------------------------------------------------

PHI_REPORT = """PATIENT NAME: John Q. Doe
MRN: 12345678   Accession: A98765432
Referring Physician: Dr. Jane Smith
DOB: 03/10/1952   Exam date: March 5, 2024
Phone: (555) 123-4567   Email: jdoe@example.com

INDICATION: 94-year-old male with chest pain.

FINDINGS:
A pulmonary nodule measures 6 mm in the right upper lobe.
Comparison to prior study dated 2024-01-02.
Images available at http://pacs.hospital.org/study/123.
"""


class TestDeidentifier:

    def setup_method(self):
        self.deid = Deidentifier()

    def test_redacts_common_phi(self):
        result = self.deid.deidentify(PHI_REPORT)
        text = result.text
        assert "John Q. Doe" not in text
        assert "12345678" not in text
        assert "A98765432" not in text
        assert "Dr. Jane Smith" not in text
        assert "jdoe@example.com" not in text
        assert "(555) 123-4567" not in text
        assert "03/10/1952" not in text
        assert "March 5, 2024" not in text
        assert "2024-01-02" not in text
        assert "http://pacs.hospital.org/study/123" not in text

    def test_preserves_clinical_content(self):
        # Measurements and findings must survive de-identification untouched.
        result = self.deid.deidentify(PHI_REPORT)
        assert "6 mm" in result.text
        assert "pulmonary nodule" in result.text.lower()
        assert "right upper lobe" in result.text.lower()

    def test_age_over_89_redacted(self):
        result = self.deid.deidentify("94-year-old male")
        assert "94" not in result.text
        assert "[AGE]" in result.text

    def test_age_under_90_preserved(self):
        # HIPAA only requires aggregating ages 90+. A 62-year-old stays.
        result = self.deid.deidentify("62-year-old female")
        assert "62-year-old" in result.text

    def test_measurement_not_treated_as_phi(self):
        result = self.deid.deidentify("Mass measures 90 mm in diameter.")
        assert "90 mm" in result.text
        assert result.redaction_count == 0

    def test_placeholder_substituted(self):
        result = self.deid.deidentify("Exam date: 03/10/2024.")
        assert "[DATE]" in result.text

    def test_redaction_offsets_map_to_original(self):
        result = self.deid.deidentify(PHI_REPORT)
        for r in result.redactions:
            assert PHI_REPORT[r.start:r.end] == r.original

    def test_redactions_non_overlapping_and_ordered(self):
        result = self.deid.deidentify(PHI_REPORT)
        last_end = -1
        for r in result.redactions:
            assert r.start >= last_end
            last_end = r.end

    def test_category_counts(self):
        result = self.deid.deidentify(PHI_REPORT)
        counts = result.category_counts()
        assert counts.get("date", 0) >= 2
        assert counts.get("email", 0) == 1
        assert counts.get("mrn", 0) == 1
        assert sum(counts.values()) == result.redaction_count

    def test_ssn_redacted(self):
        result = self.deid.deidentify("SSN 123-45-6789 on file.")
        assert "123-45-6789" not in result.text
        assert "[SSN]" in result.text

    def test_no_phi_yields_no_redactions(self):
        clean = "FINDINGS: The lungs are clear. Heart size normal."
        result = self.deid.deidentify(clean)
        assert result.redaction_count == 0
        assert result.text == clean

    def test_category_subset(self):
        # Only redact dates; leave the SSN in place.
        deid = Deidentifier(categories=["date"])
        result = deid.deidentify("03/10/2024 SSN 123-45-6789")
        assert "[DATE]" in result.text
        assert "123-45-6789" in result.text

    def test_custom_placeholder(self):
        deid = Deidentifier(placeholders={"date": "<REDACTED>"})
        result = deid.deidentify("Exam date: 03/10/2024.")
        assert "<REDACTED>" in result.text

    def test_unknown_category_raises(self):
        with pytest.raises(ValueError):
            Deidentifier(categories=["not_a_category"])

    def test_none_text_raises(self):
        with pytest.raises(ValueError):
            self.deid.deidentify(None)

    def test_module_convenience_function(self):
        result = deidentify("Exam date: 03/10/2024.")
        assert "[DATE]" in result.text

    def test_result_to_dict(self):
        result = self.deid.deidentify(PHI_REPORT)
        d = result.to_dict()
        assert "text" in d
        assert "redaction_count" in d
        assert "category_counts" in d
        assert isinstance(d["redactions"], list)

    def test_supported_categories(self):
        cats = self.deid.supported_categories
        assert "date" in cats
        assert "name" in cats
        assert "mrn" in cats

    def test_header_label_preserves_label_redacts_value(self):
        result = self.deid.deidentify("Patient Name: John Doe")
        assert "Patient Name:" in result.text
        assert "John Doe" not in result.text

    def test_multi_field_header_line_split_by_category(self):
        # A label value must stop at the column break so following fields on the
        # same line are categorized correctly rather than swallowed as one name.
        line = "PATIENT NAME: John Q. Doe    MRN: 12345678    Accession: A98765432"
        result = self.deid.deidentify(line)
        counts = result.category_counts()
        assert counts.get("name") == 1
        assert counts.get("mrn") == 1
        assert counts.get("accession") == 1
        assert "John Q. Doe" not in result.text
        assert "12345678" not in result.text


class TestDeidentifyCLI:

    def setup_method(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def _write_report(self, name, text):
        from pathlib import Path
        p = Path(self.tmp) / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_cli_deidentify_flag_scrubs_output(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout, redirect_stderr
        from radreport.cli import main

        f = self._write_report("phi.txt", PHI_REPORT)
        buf, err = StringIO(), StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            main([f, "--deidentify"])
        result = json.loads(buf.getvalue())
        # The raw text carried through the parsed output must be scrubbed.
        blob = json.dumps(result)
        assert "jdoe@example.com" not in blob
        assert "12345678" not in blob


# ---------------------------------------------------------------------------
# Interval-change comparison (ReportComparator)
# ---------------------------------------------------------------------------

PRIOR_STUDY = """
FINDINGS:
Right upper lobe pulmonary nodule measuring 6 mm.
Liver lesion measuring 1.2 cm in segment VI.
Enlarged mediastinal lymph node measuring 15 mm.
"""

CURRENT_STUDY = """
FINDINGS:
Right upper lobe pulmonary nodule measuring 9 mm, enlarged.
Liver lesion measuring 1.2 cm in segment VI, unchanged.
New 8 mm right adrenal nodule.
"""


class TestReportComparator:

    def setup_method(self):
        self.parser = ReportParser()
        self.comparator = ReportComparator()

    def _compare(self, current, prior):
        cur = self.parser.parse(current, modality="CT")
        pri = self.parser.parse(prior, modality="CT")
        return self.comparator.compare(cur, pri)

    def test_growing_lesion_flagged_increased(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        inc = result.by_status("increased")
        assert len(inc) == 1
        c = inc[0]
        assert c.prior_mm == 6.0
        assert c.current_mm == 9.0
        assert c.delta_mm == 3.0
        assert c.percent_change == 50.0

    def test_new_lesion_detected(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        new = result.by_status("new")
        assert len(new) == 1
        assert new[0].current_mm == 8.0
        assert new[0].prior_mm is None

    def test_stable_lesion(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        stable = result.by_status("stable")
        assert len(stable) == 1
        assert stable[0].delta_mm == 0.0

    def test_resolved_lesion(self):
        # The lymph node in the prior has no match in the current study.
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        resolved = result.by_status("resolved")
        assert len(resolved) == 1
        assert resolved[0].prior_mm == 15.0
        assert resolved[0].current_mm is None

    def test_has_progression_true_when_growth(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        assert result.has_progression is True

    def test_shrinking_lesion_flagged_decreased(self):
        prior = "FINDINGS:\nMass measuring 30 mm in the right lobe."
        current = "FINDINGS:\nMass measuring 20 mm in the right lobe."
        result = self._compare(current, prior)
        dec = result.by_status("decreased")
        assert len(dec) == 1
        assert dec[0].delta_mm == -10.0
        assert dec[0].percent_change < 0

    def test_small_change_within_threshold_is_stable(self):
        # 1 mm change on an 8 mm nodule clears neither the 2 mm nor 20% bar.
        prior = "FINDINGS:\nPulmonary nodule measuring 8 mm."
        current = "FINDINGS:\nPulmonary nodule measuring 9 mm."
        result = self._compare(current, prior)
        assert result.by_status("stable")
        assert not result.by_status("increased")

    def test_custom_thresholds(self):
        prior = "FINDINGS:\nPulmonary nodule measuring 8 mm."
        current = "FINDINGS:\nPulmonary nodule measuring 9 mm."
        # Lower both thresholds so a 1 mm / 12.5% change registers.
        comp = ReportComparator(min_abs_mm=1.0, min_pct=10.0)
        cur = self.parser.parse(current)
        pri = self.parser.parse(prior)
        result = comp.compare(cur, pri)
        assert result.by_status("increased")

    def test_unmeasured_findings_are_ignored(self):
        # No measurements anywhere → nothing trackable → empty comparison.
        prior = "FINDINGS:\nNo pneumothorax. Clear lungs."
        current = "FINDINGS:\nNo pneumothorax. Clear lungs."
        result = self._compare(current, prior)
        assert result.comparisons == []

    def test_status_counts(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        counts = result.status_counts()
        assert counts.get("increased") == 1
        assert counts.get("new") == 1
        assert counts.get("stable") == 1
        assert counts.get("resolved") == 1

    def test_to_dict_shape(self):
        result = self._compare(CURRENT_STUDY, PRIOR_STUDY)
        d = result.to_dict()
        assert set(d.keys()) == {"status_counts", "has_progression", "comparisons"}
        assert isinstance(d["comparisons"], list)
        assert set(d["comparisons"][0].keys()) == {
            "status", "anatomy", "current_text", "prior_text",
            "current_mm", "prior_mm", "delta_mm", "percent_change", "match_score",
        }

    def test_convenience_wrapper(self):
        result = compare_reports(CURRENT_STUDY, PRIOR_STUDY, modality="CT")
        assert result.has_progression is True


class TestCompareCLI:

    def setup_method(self):
        import tempfile
        self.tmp = tempfile.mkdtemp()

    def _write(self, name, text):
        from pathlib import Path
        p = Path(self.tmp) / name
        p.write_text(text, encoding="utf-8")
        return str(p)

    def test_cli_compare_outputs_interval_change(self):
        import json
        from io import StringIO
        from contextlib import redirect_stdout, redirect_stderr
        from radreport.cli import main

        cur = self._write("current.txt", CURRENT_STUDY)
        pri = self._write("prior.txt", PRIOR_STUDY)
        buf, err = StringIO(), StringIO()
        with redirect_stdout(buf), redirect_stderr(err):
            main([cur, "--compare", pri, "--modality", "CT"])
        result = json.loads(buf.getvalue())
        assert result["has_progression"] is True
        assert result["current_file"] == "current.txt"
        assert result["prior_file"] == "prior.txt"
        assert result["status_counts"].get("increased") == 1

    def test_cli_compare_rejects_multiple_current_files(self):
        from io import StringIO
        from contextlib import redirect_stderr
        from radreport.cli import main

        a = self._write("a.txt", CURRENT_STUDY)
        b = self._write("b.txt", CURRENT_STUDY)
        pri = self._write("prior.txt", PRIOR_STUDY)
        with redirect_stderr(StringIO()):
            with pytest.raises(SystemExit):
                main([a, b, "--compare", pri])
