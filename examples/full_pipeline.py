"""
End-to-end example: radreport full pipeline.
Run from repo root: python examples/full_pipeline.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # repo root

from radreport import (
    ReportParser, CriticalFindingsDetector, FHIRExporter, Deidentifier,
    ReportComparator, TemplateMatcher,
)

# ── Sample report ──────────────────────────────────────────────────────────────

REPORT = """
PATIENT NAME: John Q. Doe    MRN: 12345678    Accession: A98765432
Referring Physician: Dr. Jane Smith    Exam date: March 5, 2024

INDICATION: 58-year-old male with acute chest pain and shortness of breath.

TECHNIQUE: CT pulmonary angiography with IV contrast, helical acquisition.

COMPARISON: Chest X-ray from two weeks prior.

FINDINGS:
Pulmonary vasculature: There is a large saddle embolus straddling the main
pulmonary artery bifurcation extending into the bilateral main pulmonary arteries.
Right heart strain pattern noted.

Lungs: No pneumothorax. No pleural effusion. No consolidation. A 6mm right upper
lobe pulmonary nodule is noted. Lungs are otherwise clear.

Heart: The right ventricle is enlarged measuring 4.2 x 3.8 cm. The right-to-left
ventricular ratio is 1.3 (normal <0.9). No pericardial effusion.

Mediastinum: No mediastinal lymphadenopathy. No pneumomediastinum.

Bones: No acute osseous abnormality. Degenerative changes at T8-T9.

IMPRESSION:
1. Massive bilateral pulmonary embolism with saddle embolus at the main pulmonary
   artery bifurcation. Right heart strain pattern. Emergent clinical correlation
   and treatment recommended.
2. 6mm right upper lobe pulmonary nodule. Follow-up CT in 12 months recommended
   per Fleischner Society guidelines.
3. No pneumothorax.
"""

# ── Pipeline ───────────────────────────────────────────────────────────────────

parser   = ReportParser()
detector = CriticalFindingsDetector()
exporter = FHIRExporter()
deid     = Deidentifier()

print("=" * 60)
print("STEP 0: DE-IDENTIFY (PHI REDACTION)")
print("=" * 60)

deid_result = deid.deidentify(REPORT)
print(f"\nRedacted {deid_result.redaction_count} PHI span(s): "
      f"{deid_result.category_counts()}")
print("\nScrubbed header:")
for line in deid_result.text.strip().splitlines()[:2]:
    print(f"  {line}")

# Everything downstream operates on the de-identified text.
clean_report_text = deid_result.text

print("\n" + "=" * 60)
print("STEP 1: PARSE")
print("=" * 60)

report = parser.parse(clean_report_text, modality="CT")

print(f"\nModality: {report.modality}")
print(f"Sections found: {[s.name for s in report.sections]}")
print(f"\nImpression:\n{report.impression}")

print(f"\nAll measurements ({len(report.all_measurements)} found):")
for m in report.all_measurements:
    print(f"  {m.raw:25s} → {m.dimensions_mm} mm")

print(f"\nFindings by anatomy:")
findings_section = report.get_section("findings")
if findings_section:
    for f in findings_section.findings:
        if f.anatomy:
            print(f"  [{f.anatomy:20s}] {f.text[:80]}...")

print("\n" + "=" * 60)
print("STEP 2: CRITICAL FINDINGS DETECTION")
print("=" * 60)

report = detector.detect(report)

active   = [cf for cf in report.critical_findings if not cf.negated]
negated  = [cf for cf in report.critical_findings if cf.negated]

print(f"\nActive critical findings ({len(active)}):")
for cf in active:
    icon = "🔴" if cf.severity == "critical" else "🟡" if cf.severity == "urgent" else "🔵"
    print(f"\n  {icon} [{cf.severity.upper()}] {cf.term}")
    print(f"     Category : {cf.category}")
    print(f"     Context  : {cf.context[:100]}...")

print(f"\nNegated findings (not alerted, {len(negated)}):")
for cf in negated:
    print(f"  ✓ {cf.term} (negated)")

print("\n" + "=" * 60)
print("STEP 3: FHIR EXPORT")
print("=" * 60)

fhir = exporter.export(report, patient_id="pt-12345")

print(f"\nFHIR Resource: {fhir['resourceType']}")
print(f"Status       : {fhir['status']}")
print(f"LOINC code   : {fhir['code']['coding'][0]['code']}")
print(f"Patient ref  : {fhir.get('subject', {}).get('reference', 'none')}")
print(f"Contained obs: {len(fhir.get('contained', []))}")
print(f"Sections     : {len(fhir.get('extension', []))}")

# Write full FHIR output to file
output_path = os.path.join(os.path.dirname(__file__), "output_fhir.json")
with open(output_path, "w") as f:
    json.dump(fhir, f, indent=2)

print(f"\nFull FHIR JSON written to: {output_path}")

print("\n" + "=" * 60)
print("STEP 4: INTERVAL CHANGE vs PRIOR STUDY")
print("=" * 60)

# A follow-up CT performed some months later. Same patient, new numbers.
PRIOR = """
FINDINGS:
Right upper lobe pulmonary nodule measuring 4 mm.
No adrenal nodule.
"""

FOLLOW_UP = """
FINDINGS:
Right upper lobe pulmonary nodule measuring 7 mm, interval enlargement.
New 9 mm left adrenal nodule.
"""

comparator = ReportComparator()
prior_report  = parser.parse(PRIOR, modality="CT")
follow_report = parser.parse(FOLLOW_UP, modality="CT")
change = comparator.compare(follow_report, prior_report)

print(f"\nStatus counts : {change.status_counts()}")
print(f"Progression   : {change.has_progression}")
for c in change.comparisons:
    if c.prior_mm is not None and c.current_mm is not None:
        detail = f"{c.prior_mm} → {c.current_mm} mm ({c.percent_change:+.0f}%)"
    else:
        detail = f"{c.current_mm or c.prior_mm} mm"
    print(f"  [{c.status:9s}] {c.anatomy or 'unspecified':12s} {detail}")

print("\n" + "=" * 60)
print("STEP 5: TEMPLATE COMPLETENESS CHECK")
print("=" * 60)

# Reuse the parsed CT chest report from Step 1. Auto-selects the best template.
matcher = TemplateMatcher()
match = matcher.match(report)  # template="auto"

print(f"\nTemplate      : {match.template_name} ({match.template_key})")
print(f"Auto-selected : {match.auto_selected} "
      f"(score {match.classification_score})")
print(f"Completeness  : {match.completeness:.0%}")
print(f"Covered       : {[i.key for i in match.covered_items]}")
print(f"Missing (req.): {[i.key for i in match.missing_items]}")

print("\nDone.")
