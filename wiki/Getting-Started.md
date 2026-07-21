# Getting Started

## Install

```bash
pip install radreport
```

Zero required dependencies. Works on Python 3.9+. For development extras
(pytest), install `radreport[dev]`.

## Your first parse

```python
from radreport import ReportParser

text = """
INDICATION: Chest pain, rule out PE.

FINDINGS:
Lungs: Filling defect in the right main pulmonary artery consistent with
pulmonary embolism. No pneumothorax. A 6 mm right upper lobe nodule.

IMPRESSION:
Pulmonary embolism, right main pulmonary artery. Follow-up CT in 12 months.
"""

report = ReportParser().parse(text, modality="CT")

print(report.impression)
print([s.name for s in report.sections])
print([(m.raw, m.dimensions_mm) for m in report.all_measurements])
```

## The full pipeline

Each capability is a small, composable step. Instantiate the pieces you need and
chain them:

```python
from radreport import (
    ReportParser, CriticalFindingsDetector, RecommendationExtractor,
    TemplateMatcher, Deidentifier, FHIRExporter,
)

raw = "...report text..."

# 1. Optionally scrub PHI first, so everything downstream is safe to share.
raw = Deidentifier().deidentify(raw).text

# 2. Parse.
report = ReportParser().parse(raw, modality="CT")

# 3. Enrich (each mutates and returns the same report).
report = CriticalFindingsDetector().detect(report)
report = RecommendationExtractor().extract(report)

# 4. Assess completeness (returns a standalone result — does not mutate report).
match = TemplateMatcher().match(report)

# 5. Export.
fhir = FHIRExporter().export(report, patient_id="pt-001")
```

## Serialization

Everything the library returns is a dataclass with a `to_dict()`:

```python
report.to_dict()        # nested dict, JSON-ready
report.to_json(indent=2)
report.to_flat_dict()   # one flat row per report — ideal for CSV / pandas
match.to_dict()
```

## Next steps

- [CLI Reference](CLI-Reference) — do all of the above from the shell.
- [Report Templates](Report-Templates) — the newest capability.
- [API Reference](API-Reference) — full surface area.
