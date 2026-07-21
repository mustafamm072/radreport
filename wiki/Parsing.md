# Parsing

`ReportParser` turns free text into a `ParsedReport` — labeled sections,
normalized measurements, and findings linked to anatomy.

```python
from radreport import ReportParser

report = ReportParser().parse(text, modality="CT")
```

## Sections

Headers are recognized on line starts (case-insensitive), regardless of styling:

| Section key | Matched headers |
|-------------|-----------------|
| `indication` | Indication, Clinical Indication, History, Reason for Exam |
| `technique` | Technique, Procedure, Protocol, Method |
| `comparison` | Comparison, Prior Study, Prior Exam, Previous |
| `findings` | Findings, Observations, Result |
| `impression` | Impression, Conclusion, Summary, Assessment, Diagnosis |
| `recommendation` | Recommendation, Follow-up, Advised |

Text before the first header is kept as `preamble`. If no headers are found, the
whole report is treated as `findings`.

```python
report.get_section("findings").raw_text      # case-insensitive lookup
report.impression                              # convenience shortcut
```

## Measurements

All measurements are normalized to **millimeters**:

```python
for m in report.all_measurements:
    m.raw                    # "2.3 x 1.8 cm"
    m.dimensions_mm          # [23.0, 18.0]
    m.largest_dimension_mm   # 23.0
    m.unit_original          # "cm"
```

Handles `12mm`, `1.2 cm`, `1.2 x 0.8 cm`, `12 x 8 x 5 mm`, and inches (`in`).
Units beyond mm/cm/in (cc, mL, HU) are not extracted — see [Known Issues](Known-Issues).

## Findings by anatomy

For `findings` and `impression` sections, each sentence becomes a `Finding`,
tagged with the first matching anatomy keyword and carrying its own measurements:

```python
for f in report.get_section("findings").findings:
    f.text, f.anatomy, f.measurements
```

## Batch & serialization

```python
reports = ReportParser().parse_batch([t1, t2, t3], modality="CT")
active  = [r for r in reports if r is not None]   # None = empty/unparseable

report.to_dict()          # nested, JSON-ready
report.to_json(indent=2)
report.to_flat_dict()     # one flat row — for CSV / pandas
```

`parse()` raises `ValueError` on empty input; `parse_batch()` yields `None` for
those entries instead of raising.
