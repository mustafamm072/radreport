"""
Tests for radreport-parser.
Run with: pytest tests/ -v
"""

import pytest

from radreport_parser import ReportParser, CriticalFindingsDetector, FHIRExporter, RecommendationExtractor

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
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main

        f1 = self._write_report("r1.txt", CT_CHEST_REPORT)
        f2 = self._write_report("r2.txt", NORMAL_XRAY_REPORT)
        buf = StringIO()
        with redirect_stdout(buf):
            main([f1, f2])
        result = json.loads(buf.getvalue())
        assert isinstance(result, list)
        assert len(result) == 2

    def test_cli_missing_file_exits(self):
        from radreport_parser.cli import main
        with pytest.raises(SystemExit):
            main(["/nonexistent/path/report.txt"])

    def test_cli_output_file(self):
        import json
        from pathlib import Path
        from io import StringIO
        from contextlib import redirect_stdout, redirect_stderr
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main

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
        from radreport_parser.cli import main
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
