# API Reference

Everything below is importable directly from `radreport`.

## Processors

| Class / function | Entry point | Returns |
|------------------|-------------|---------|
| `ReportParser` | `.parse(text, modality=None)` · `.parse_batch(texts, modality=None)` | `ParsedReport` (or `None` in batch) |
| `CriticalFindingsDetector` | `.detect(report)` | same `ParsedReport` (mutated) |
| `RecommendationExtractor` | `.extract(report)` | same `ParsedReport` (mutated) |
| `ReportComparator` | `.compare(current, prior)` | `ComparisonResult` |
| `compare_reports` | `(current_text, prior_text, modality=None, **kw)` | `ComparisonResult` |
| `TemplateMatcher` | `.match(report, template="auto")` · `.classify(report)` · `.available` | `TemplateMatch` / `str` / `list[str]` |
| `match_template` | `(text, template="auto", modality=None, **kw)` | `TemplateMatch` |
| `Deidentifier` | `.deidentify(text)` | `DeidentificationResult` |
| `deidentify` | `(text, **kw)` | `DeidentificationResult` |
| `FHIRExporter` | `.export(report, patient_id=None, report_id=None, issued_dt=None)` | `dict` (FHIR R4) |

The three enrichers (`detect`, `extract`) mutate and return the same
`ParsedReport`. The comparator, template matcher, and de-identifier return their
own standalone result objects and never mutate the report.

## Schema dataclasses

Every schema type has `to_dict()`.

- **`ParsedReport`** — `raw_text`, `sections`, `impression`, `findings_text`,
  `all_measurements`, `modality`, `critical_findings`, `recommendations`.
  Methods: `get_section(name)`, `to_dict()`, `to_json(indent=2)`, `to_flat_dict()`.
- **`ReportSection`** — `name`, `raw_text`, `findings`, `measurements`.
- **`Finding`** — `text`, `anatomy`, `measurements`.
- **`Measurement`** — `raw`, `dimensions_mm`, `unit_original`; props `is_single`,
  `largest_dimension_mm`.
- **`CriticalFinding`** — `term`, `category`, `severity`, `context`, `negated`.
- **`FollowUpRecommendation`** — `text`, `interval`, `modality`, `urgency`.
- **`FindingComparison`** — `status`, `anatomy`, `current_text`, `prior_text`,
  `current_mm`, `prior_mm`, `delta_mm`, `percent_change`, `match_score`.
- **`ComparisonResult`** — `comparisons`; `by_status(s)`, `status_counts()`,
  `has_progression`.
- **`TemplateItemResult`** — `key`, `label`, `covered`, `required`, `matched_keyword`.
- **`TemplateMatch`** — `template_key`, `template_name`, `auto_selected`,
  `classification_score`, `items`; props `covered_items`, `missing_items`,
  `completeness`, `is_complete`; `to_dict()`, `to_flat_dict()`.
- **`Redaction`** — `category`, `original`, `replacement`, `start`, `end`.
- **`DeidentificationResult`** — `text`, `redactions`; `redaction_count`,
  `category_counts()`.

## Template definitions

- **`ReportTemplate`** (`key`, `name`, `modalities`, `classifier_keywords`, `items`)
- **`TemplateItem`** (`key`, `label`, `keywords`, `required=True`)
- **`TEMPLATES`** — dict of built-in templates keyed by key.

## Module-level data

- `radreport.critical_findings.CRITICAL_TERMS` — editable `term → (category, severity)`.
- `radreport.__version__` — the installed version string.
