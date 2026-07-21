# Interval Change (Prior Comparison)

The most common question asked of a follow-up study is *"is the lesion growing?"*
`ReportComparator` answers it: given a current and a prior report, it classifies
every **measurable** finding with the standard interval-change vocabulary —
**new**, **increased**, **decreased**, **stable**, **resolved**.

```python
from radreport import compare_reports

result = compare_reports(current_text, prior_text, modality="CT")

result.has_progression        # True if anything is new or increased
result.status_counts()        # {"increased": 1, "new": 1, "stable": 1, ...}

for c in result.comparisons:
    if c.status in ("increased", "decreased"):
        print(c.anatomy, c.prior_mm, "→", c.current_mm, f"({c.percent_change:+.0f}%)")
    else:
        print(c.anatomy, c.status)
```

From parsed reports:

```python
from radreport import ReportParser, ReportComparator

p = ReportParser()
result = ReportComparator().compare(p.parse(cur, "CT"), p.parse(pri, "CT"))
```

## How matching works

- **Measurable findings only.** A finding must carry an extractable measurement
  to be tracked. Qualitative statements are out of scope.
- **Pairing.** Findings are paired across studies by anatomy + token-overlap
  score, greedily and one-to-one. Leftover current findings → `new`; leftover
  prior findings → `resolved`.
- **Thresholds.** A change is called `increased`/`decreased` only when it clears
  **both** an absolute (default 2 mm) and a relative (default 20%) bar —
  suppressing measurement jitter. Everything else is `stable`.

## Tuning

```python
ReportComparator(min_abs_mm=3.0, min_pct=30.0, min_match_score=0.15)
```

Every `FindingComparison` is auditable: it records `prior_text`, `current_text`,
`prior_mm`, `current_mm`, `delta_mm`, `percent_change`, and the `match_score` it
was derived from.

## CLI

```bash
radreport current.txt --compare prior.txt --modality CT
```

> Decision support only. Thresholds are generic (loosely RECIST/Fleischner-
> inspired), not a certified society guideline, and matching is text-based — see
> [Known Issues](Known-Issues).
