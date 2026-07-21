# FHIR Export

`FHIRExporter` outputs a valid FHIR R4 `DiagnosticReport` resource as a plain
Python dict, ready to serialize and load into any FHIR server.

```python
from datetime import datetime
from radreport import FHIRExporter

fhir = FHIRExporter().export(
    report,
    patient_id="pt-001",       # optional: links to a FHIR Patient
    report_id="rpt-20240315",  # optional: custom resource ID (else a UUID)
    issued_dt=datetime.now(),  # optional: defaults to UTC now
)
```

## What's included

| Element | Value |
|---------|-------|
| `resourceType` | `DiagnosticReport` |
| `status` | `final` |
| `category` | Radiology (`RAD`) |
| `code` | LOINC code matched to modality |
| `conclusion` | impression text |
| `presentedForm` | full report text as a base64 attachment |
| `contained` | `Observation` per active (non-negated) critical finding |
| `result` | references to the contained observations |
| `extension` | structured sections for downstream parsing |
| `subject` | `Patient/{patient_id}` when provided |

Run [critical findings detection](Critical-Findings) before exporting to populate
the contained observations (the CLI's `--fhir` implies `--critical`).

## Caveats

- Uses **unspecified-body-region** LOINC codes per modality — it does not resolve
  the specific body-region LOINC.
- Extension URLs use an `example.org` placeholder namespace; replace with your own
  canonical URLs for production.
- `ImagingStudy` / `Condition` resources are on the roadmap, not yet implemented.

See [Known Issues](Known-Issues).
