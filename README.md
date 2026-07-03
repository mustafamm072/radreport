# radreport

**Parse radiology free-text reports into structured data. No ML. No GPU. No dependencies.**

[![PyPI](https://img.shields.io/pypi/v/radreport)](https://pypi.org/project/radreport/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21147298.svg)](https://doi.org/10.5281/zenodo.21147298)

Radiology reports come out as free-text PDFs. Downstream systems — EMRs, telehealth portals, billing platforms, research pipelines — need structured data. This library bridges that gap.

Four things it does well:

1. **Parse** — splits any free-text report into labeled sections, extracts measurements, links findings to anatomy
2. **Detect** — flags critical/urgent findings with negation awareness (no false alerts for "no pneumothorax")
3. **De-identify** — redacts PHI (dates, MRNs, names, contact info…) with a full audit trail, so reports can leave a controlled environment for research
4. **Export** — outputs FHIR R4 DiagnosticReport resources ready for any EMR

---

## Install

```bash
pip install radreport
```

Zero required dependencies. Works on Python 3.9+.

---

## Quick Start

```python
from radreport import ReportParser, CriticalFindingsDetector, FHIRExporter
import json

report_text = """
INDICATION: Chest pain, rule out PE.

FINDINGS:
Lungs: Filling defect in the right main pulmonary artery consistent with
pulmonary embolism. No pneumothorax.

IMPRESSION:
Pulmonary embolism, right main pulmonary artery. Urgent correlation recommended.
"""

# 1. Parse
parser = ReportParser()
report = parser.parse(report_text, modality="CT")

print(report.impression)
# → "Pulmonary embolism, right main pulmonary artery. Urgent correlation recommended."

# 2. Detect critical findings
detector = CriticalFindingsDetector()
report = detector.detect(report)

for cf in report.critical_findings:
    if not cf.negated:
        print(f"[{cf.severity.upper()}] {cf.term} ({cf.category})")
        print(f"  Context: {cf.context}")
# → [CRITICAL] pulmonary embolism (pulmonary)
#     Context: Filling defect in the right main pulmonary artery consistent with pulmonary embolism.

# 3. Export to FHIR
exporter = FHIRExporter()
fhir = exporter.export(report, patient_id="pt-001")
print(json.dumps(fhir, indent=2))
```

---

## CLI

After installation, the `radreport` command is available for single-file and batch processing:

```bash
# Parse a single report to JSON
radreport report.txt

# Parse with critical findings detection
radreport report.txt --critical

# Export as FHIR DiagnosticReport
radreport report.txt --fhir --patient-id pt-001 --modality CT

# Extract follow-up recommendations too
radreport report.txt --critical --recommend

# Redact PHI before parsing (safe to store/share the output)
radreport report.txt --deidentify --critical

# Batch process multiple files → JSON array
radreport reports/*.txt --critical -o batch.json

# Specify modality for all files
radreport *.txt --modality MRI --fhir -o fhir_batch.json

# Flat CSV for research/analytics (one row per report)
radreport reports/*.txt --critical --recommend --format csv -o cohort.csv
```

**Flags:**

| Flag | Short | Description |
|------|-------|-------------|
| `--modality MOD` | `-m` | CT, MRI, XR, US, NM, PET … |
| `--critical` | `-c` | Run critical findings detection |
| `--recommend` | `-r` | Extract follow-up imaging recommendations |
| `--deidentify` | `-d` | Redact PHI (dates, MRN, names, phone…) before parsing |
| `--fhir` | `-f` | Export as FHIR R4 DiagnosticReport (implies --critical) |
| `--patient-id ID` | | FHIR Patient resource ID (used with `--fhir`) |
| `--format FMT` | `--fmt` | Output format: `json` (default) or `csv` (not compatible with `--fhir`) |
| `--output FILE` | `-o` | Write output to file instead of stdout |

---

## Parsing

### Sections

The parser recognizes standard radiology report sections regardless of formatting style:

| Section key      | Matched headers |
|------------------|-----------------|
| `indication`     | Indication, Clinical Indication, History, Reason for Exam |
| `technique`      | Technique, Procedure, Protocol |
| `comparison`     | Comparison, Prior Study, Previous |
| `findings`       | Findings, Observations |
| `impression`     | Impression, Conclusion, Assessment, Diagnosis |
| `recommendation` | Recommendation, Follow-up, Advised |

```python
report = parser.parse(text, modality="MRI")

findings = report.get_section("findings")
print(findings.raw_text)

impression = report.get_section("impression")
print(impression.raw_text)
```

### Measurements

All measurements are extracted and normalized to millimeters:

```python
for m in report.all_measurements:
    print(f"  Raw: {m.raw}")
    print(f"  Normalized (mm): {m.dimensions_mm}")
    print(f"  Largest dimension: {m.largest_dimension_mm} mm")

# Raw: 2.3 x 1.8 cm
# Normalized (mm): [23.0, 18.0]
# Largest dimension: 23.0 mm
```

Handles: `1.2 x 0.8 cm`, `12mm`, `1.2cm`, `12 x 8 x 5 mm`, `1.2 x 0.8 x 0.5 cm`

### Findings by anatomy

```python
findings_section = report.get_section("findings")
for finding in findings_section.findings:
    print(f"Anatomy: {finding.anatomy or 'unspecified'}")
    print(f"Text: {finding.text}")
```

### Batch processing

```python
reports = parser.parse_batch(list_of_texts, modality="CT")
# Returns list[ParsedReport | None] — None for empty/unparseable inputs
active = [r for r in reports if r is not None]
```

### JSON serialization

```python
report = parser.parse(text, modality="CT")

# As dict
d = report.to_dict()

# As JSON string (shorthand)
json_str = report.to_json()
json_str = report.to_json(indent=4)
```

---

## Critical Findings Detection

Rule-based. Fully auditable. No black boxes.

Covers 45+ terms across 7 categories:

| Category    | Examples |
|-------------|----------|
| `vascular`  | aortic dissection, DVT, aortic aneurysm |
| `pulmonary` | pulmonary embolism, PE, pneumothorax, hemothorax |
| `neuro`     | subdural hematoma, midline shift, intracranial hemorrhage |
| `abdominal` | free air, bowel perforation, appendicitis |
| `cardiac`   | cardiac tamponade, pericardial effusion |
| `spinal`    | cord compression, cervical fracture |
| `oncologic` | malignancy, metastasis, carcinoma |

### Negation awareness

```python
# "No pneumothorax identified" → negated=True, won't trigger alert
# "Pneumothorax present" → negated=False, triggers alert

active = [cf for cf in report.critical_findings if not cf.negated]
```

Negation is **scoped to the sentence** and **fails safe**:

- A negation in one sentence never carries into the next — *"No acute hemorrhage.
  Large subdural hematoma is present."* flags the hematoma as active.
- When a term appears more than once, an active (non-negated) mention always wins
  over a negated one — *"No pneumothorax at the apex. Large pneumothorax at the
  base."* flags pneumothorax as active. A term is reported as negated only when
  **every** mention is negated. This prevents a real critical finding from being
  silently suppressed by an earlier "no ..." phrase.

### Severity levels

- `critical` — requires immediate action (PE, subdural hematoma, pneumothorax)
- `urgent` — requires same-day follow-up (DVT, bowel obstruction, appendicitis)
- `significant` — requires follow-up (malignancy, metastasis)

### Extending the term list

```python
from radreport.critical_findings import CRITICAL_TERMS

CRITICAL_TERMS["tension pneumothorax"] = ("pulmonary", "critical")
CRITICAL_TERMS["septic emboli"] = ("vascular", "urgent")
```

---

## Follow-up Recommendations

Extract structured follow-up imaging recommendations from the recommendation and
impression sections — interval, modality, and urgency.

```python
from radreport import ReportParser, RecommendationExtractor

report = ReportParser().parse(text, modality="CT")
report = RecommendationExtractor().extract(report)

for rec in report.recommendations:
    print(rec.interval, rec.modality, rec.urgency)

# "Recommend follow-up CT in 6 months."
# → interval="6 months", modality="CT", urgency="routine"
```

Negation-aware: *"No follow-up imaging indicated"* yields no recommendation.
Identical recommendations are deduplicated.

---

## De-identification

Strip Protected Health Information (PHI) from a report before it leaves a
controlled environment — for research collaboration, analytics warehouses, or
off-site processing. Like everything else in this library, it is **rule-based
and fully auditable**: every removal is a traceable regular-expression match,
recorded with its original offset. No ML, no cloud NER service — the kind of
thing hospital IT will actually approve.

```python
from radreport import Deidentifier

deid = Deidentifier()
result = deid.deidentify(raw_report_text)

print(result.text)              # scrubbed report, safe to share
print(result.redaction_count)   # e.g. 11
print(result.category_counts()) # {"date": 3, "mrn": 1, "name": 2, ...}

# Audit trail — every removed span, keyed to the original text
for r in result.redactions:
    print(r.category, r.original, "→", r.replacement, f"@{r.start}:{r.end}")
```

### What it detects

Categories map to the HIPAA Safe Harbor identifiers that are reliably matchable
from text alone:

| Category | Examples |
|----------|----------|
| `date` | `03/10/2024`, `2024-03-10`, `March 5, 2024` |
| `age` | ages **90+** (`94-year-old`) — HIPAA requires aggregating these |
| `ssn` | `123-45-6789` |
| `mrn` | `MRN: 12345678`, `Medical Record Number 12345678` |
| `accession` | `Accession: A98765432` |
| `phone` | `(555) 123-4567`, `555-123-4567` |
| `email` | `jdoe@example.com` |
| `url` | `http://pacs.hospital.org/...` |
| `ipv4` | `10.0.0.1` |
| `zip` | `DC 20500` (ZIP after a state code) |
| `name` | titled names (`Dr. Jane Smith`) and header fields (`Patient Name: …`) |

Clinical content is preserved: a `6 mm` nodule or a `90 mm` mass is never
mistaken for PHI, because age matching requires an explicit age cue.

### Configuration

```python
# Redact only dates and names, and use a custom placeholder for names
deid = Deidentifier(
    categories=["date", "name"],
    placeholders={"name": "XXXX"},
)
```

> **Scope and limitations.** Rule-based de-identification is a strong first pass,
> not a compliance guarantee. Names that appear in free narrative **without** a
> title or header label are not caught. Always review the output before PHI
> leaves a controlled environment. This tool does not certify HIPAA Safe Harbor
> compliance.

---

## FHIR Export

Outputs a valid FHIR R4 `DiagnosticReport` resource.

```python
from datetime import datetime

fhir = exporter.export(
    report,
    patient_id="pt-001",       # Optional: links to FHIR Patient resource
    report_id="rpt-20240315",   # Optional: custom resource ID
    issued_dt=datetime.now(),   # Optional: defaults to UTC now
)
```

### What's included

- `resourceType`: `DiagnosticReport`
- `status`: `final`
- `code`: LOINC code matched to modality (CT, MRI, US, etc.)
- `conclusion`: impression text
- `presentedForm`: full report text as base64 attachment
- `contained`: FHIR Observations for each active (non-negated) critical finding
- `extension`: structured sections for downstream parsing
- `subject`: patient reference (when `patient_id` provided)

---

## Full Pipeline Example

```python
import json
from radreport import ReportParser, CriticalFindingsDetector, FHIRExporter

parser   = ReportParser()
detector = CriticalFindingsDetector()
exporter = FHIRExporter()

def process_report(text: str, modality: str, patient_id: str) -> dict:
    report = parser.parse(text, modality=modality)
    report = detector.detect(report)

    active_criticals = [cf for cf in report.critical_findings if not cf.negated]
    if active_criticals:
        print(f"WARNING: {len(active_criticals)} critical finding(s) detected")

    return exporter.export(report, patient_id=patient_id)

fhir_json = process_report(report_text, modality="CT", patient_id="pt-001")
print(json.dumps(fhir_json, indent=2))
```

See [examples/full_pipeline.py](examples/full_pipeline.py) for a runnable end-to-end example.

---

## Design Principles

**No dependencies.** The library installs with no third-party packages. This matters in hospital environments where every dependency goes through security review.

**Rule-based, not ML-based.** Every decision the library makes is traceable to a specific rule. No model weights, no GPU, no probabilistic outputs. Clinical teams can audit exactly why a finding was flagged.

**Negation-aware.** A library that can't distinguish "no pneumothorax" from "pneumothorax" is dangerous in clinical contexts. Negation detection is built into the core.

**Auditable de-identification.** PHI redaction runs locally with no ML and no external calls, and every removed span is logged with its original offset — so a privacy officer can review exactly what left the building and why.

**FHIR-first output.** Every modern EMR speaks FHIR. The export format is designed to drop into existing integrations without transformation.

---

## Running Tests

```bash
pip install radreport[dev]
pytest tests/ -v
```

---

## Roadmap

- [x] CLI tool for single-file and batch processing (`radreport` command)
- [x] `parse_batch()` API for processing lists of reports
- [x] `to_json()` convenience method on `ParsedReport`
- [x] Structured output for follow-up recommendations (`RecommendationExtractor`)
- [x] CSV export mode for research/analytics workflows (`--format csv`)
- [x] Rule-based PHI de-identification with audit trail (`Deidentifier`)
- [ ] Template matching for common report types (Chest XR, CT Abdomen, MRI Brain)
- [ ] Structured comparison / prior-study extraction (new / increased / stable / resolved)
- [ ] Additional FHIR resource types (ImagingStudy, Condition)

---

## Citation

If you use radreport in research, please cite it:

```bibtex
@software{merchant_radreport,
  author  = {Merchant, Mustafa},
  title   = {radreport: A rule-based Python library for parsing, de-identifying, and structuring radiology free-text reports to FHIR},
  url     = {https://github.com/mustafamm072/radreport},
  doi     = {10.5281/zenodo.21147298}
}
```

See [CITATION.cff](CITATION.cff) for full citation metadata.

---

## Disclaimer

This library is a developer tool for structuring report text. It is **not** a medical device and is **not** intended for direct clinical decision-making. Critical findings detection is designed to assist human review workflows, not replace radiologist judgment.

---

## License

MIT
