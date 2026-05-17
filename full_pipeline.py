"""
End-to-end example: radreport-parser full pipeline.
Run: python examples/full_pipeline.py
"""

import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from radreport_parser import ReportParser, CriticalFindingsDetector, FHIRExporter

# ── Sample report ──────────────────────────────────────────────────────────────

REPORT = """
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

print("=" * 60)
print("STEP 1: PARSE")
print("=" * 60)

report = parser.parse(REPORT, modality="CT")

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
print("\nDone.")
