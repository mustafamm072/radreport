# radreport

**Parse radiology free-text reports into structured data. No ML. No GPU. No dependencies.**

Radiology reports come out as free-text PDFs and dictations. Downstream systems —
EMRs, telehealth portals, billing platforms, research pipelines — need structured
data. radreport bridges that gap with a small, auditable, rule-based library that
installs with **zero required dependencies** and runs anywhere Python 3.9+ runs.

## What it does

1. **[Parse](Parsing)** — labeled sections, normalized measurements, findings linked to anatomy.
2. **[Detect](Critical-Findings)** — critical/urgent findings with sentence-scoped negation awareness.
3. **[Recommend](Follow-up-Recommendations)** — structured follow-up imaging (interval, modality, urgency).
4. **[Compare](Interval-Change)** — interval change vs a prior study (new / increased / decreased / stable / resolved).
5. **[Check](Report-Templates)** — completeness against a structured template for the study type.
6. **[De-identify](De-identification)** — rule-based PHI redaction with a full audit trail.
7. **[Export](FHIR-Export)** — FHIR R4 `DiagnosticReport` resources.

## Why rule-based

Every decision the library makes is traceable to a specific rule — no model
weights, no probabilistic outputs, no external calls. Clinical teams can audit
exactly *why* a finding was flagged or a span was redacted, and the library
passes hospital IT/security review precisely because it has no dependencies and
sends no data anywhere.

## Start here

- New to the library? → **[Getting Started](Getting-Started)**
- Command line? → **[CLI Reference](CLI-Reference)**
- Looking for a class or function? → **[API Reference](API-Reference)**
- What it *can't* do? → **[Known Issues](Known-Issues)**

> **Not a medical device.** radreport is a developer tool for structuring report
> text. It is decision support for human review workflows, not a substitute for
> radiologist interpretation.
