# Critical Findings Detection

`CriticalFindingsDetector` scans the clinically meaningful sections and flags
critical / urgent / significant findings. Rule-based and fully auditable.

```python
from radreport import ReportParser, CriticalFindingsDetector

report = ReportParser().parse(text, modality="CT")
report = CriticalFindingsDetector().detect(report)   # mutates + returns report

active = [cf for cf in report.critical_findings if not cf.negated]
for cf in active:
    print(cf.severity, cf.category, cf.term, "→", cf.context)
```

## Categories & severity

45+ terms across `vascular`, `pulmonary`, `neuro`, `abdominal`, `cardiac`,
`spinal`, and `oncologic`. Severity is one of:

- `critical` — immediate action (PE, subdural hematoma, pneumothorax)
- `urgent` — same-day follow-up (DVT, bowel obstruction, appendicitis)
- `significant` — needs follow-up (malignancy, metastasis)

## Negation awareness

Negation is **scoped to the sentence** and **fails safe**:

- A negation in one sentence never carries into the next: *"No acute hemorrhage.
  Large subdural hematoma present."* → hematoma flagged **active**.
- When a term appears more than once, an active mention always wins over a
  negated one. A term is reported as `negated=True` only when **every** mention
  is negated — so a real critical finding is never silently suppressed.

This intentionally errs toward over-alerting rather than under-alerting. It does
not model hedging ("cannot exclude") or double negation — see [Known Issues](Known-Issues).

## Extending the vocabulary

```python
from radreport.critical_findings import CRITICAL_TERMS

CRITICAL_TERMS["tension pneumothorax"] = ("pulmonary", "critical")
CRITICAL_TERMS["septic emboli"] = ("vascular", "urgent")
```

`CriticalFindingsDetector().supported_terms` lists everything currently monitored.

Active (non-negated) findings become contained `Observation`s in
[FHIR export](FHIR-Export).
