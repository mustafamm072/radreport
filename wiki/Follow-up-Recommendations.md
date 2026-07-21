# Follow-up Recommendations

`RecommendationExtractor` pulls structured follow-up imaging recommendations from
the recommendation and impression sections — interval, modality, and urgency.

```python
from radreport import ReportParser, RecommendationExtractor

report = ReportParser().parse(text, modality="CT")
report = RecommendationExtractor().extract(report)   # mutates + returns report

for rec in report.recommendations:
    rec.text       # original sentence
    rec.interval   # "6 months", "1 year", "annual", "short-term", ...
    rec.modality   # "CT", "MRI", "US", "XR", "PET", "NM", "mammography"
    rec.urgency    # "routine" | "urgent"
```

Example: *"Recommend follow-up CT in 6 months."* →
`interval="6 months", modality="CT", urgency="routine"`.

## Behavior

- **Negation-aware.** *"No follow-up imaging indicated"*, *"not required"*, and
  *"no repeat"* yield no recommendation.
- **Deduplicated.** Identical sentences are collapsed.
- **Interval normalization.** Numeric intervals are normalized (`6-month` →
  `6 months`); `annual`, `biannual`, and `short-term` are recognized as keywords.

These are decision-support aids; clinical judgement governs actual scheduling.
