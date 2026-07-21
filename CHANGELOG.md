# Changelog

All notable changes to this project are documented here.

## [0.6.0] - 2026-07-20

### Added
- **Structured report templates & completeness checking (`TemplateMatcher`).**
  Checks whether a report actually addressed the anatomic structures expected
  for its study type — the free-text analogue of structured-reporting
  checklists (RSNA RadReport / ACR-style). Given a parsed report it (1) picks
  the best-fit template by modality + body-region keywords, or uses a template
  you name, and (2) reports, item by item, whether each expected structure was
  covered, with an overall `completeness` score.
  - Ships five built-in templates: Chest Radiograph (`chest_xr`), CT Chest
    (`ct_chest`), CT Abdomen and Pelvis (`ct_abdomen_pelvis`), CT Head
    (`ct_head`), and MRI Brain (`mri_brain`).
  - Rule-based and fully auditable: every coverage decision records the exact
    keyword that matched. No ML, no external calls. Templates are checked only
    against the findings/impression text, so a structure named in the clinical
    history alone does not count as "addressed".
  - Optional items (e.g. contrast enhancement) do not count against
    completeness when absent. Registry is extensible — pass your own templates
    to `TemplateMatcher(templates=...)` without mutating the built-ins.
  - New schema types `TemplateItemResult` and `TemplateMatch`
    (`.completeness`, `.missing_items`, `.covered_items`, `.is_complete`,
    `.to_dict()`, `.to_flat_dict()`); definition types `ReportTemplate` and
    `TemplateItem`; and the `TEMPLATES` registry.
  - Convenience wrapper `match_template(text, template="auto", modality=...)`
    and top-level exports of all of the above.
- **CLI `--template [NAME]` and `--list-templates`.** `--template` with a key
  (or no value to auto-select) adds a `template` block to JSON output and
  completeness columns to CSV output; `--list-templates` prints the available
  template keys.

Non-breaking: existing schemas and their `to_dict`/`to_flat_dict` output are
unchanged. Template matching is a separate, opt-in step that returns its own
result object and never mutates `ParsedReport`.

## [0.5.0] - 2026-07-14

### Added
- **Interval-change comparison (`ReportComparator`).** Compares a current report
  against a prior study and classifies every *measurable* finding with the
  standard radiology vocabulary: **new / increased / decreased / stable /
  resolved**. This answers the central question of any follow-up study — *is the
  lesion growing?* — the basis of tumor-response (RECIST-style) and nodule
  surveillance (Fleischner-style) workflows.
  - Rule-based and fully auditable: findings are paired across studies by a
    transparent anatomy + token-overlap score, and each `FindingComparison`
    records the prior/current text, largest dimensions, absolute delta, and
    percent change it was derived from. No ML, no embeddings, no external calls.
  - Change is only called "increased"/"decreased" when it clears **both** an
    absolute (default 2 mm) and a relative (default 20%) threshold, suppressing
    measurement jitter on small lesions. All thresholds are constructor-configurable.
  - New schema types `FindingComparison` and `ComparisonResult`
    (`.status_counts()`, `.by_status()`, `.has_progression`, `.to_dict()`).
  - Convenience wrapper `compare_reports(current_text, prior_text, modality=...)`
    and top-level exports of `ReportComparator`, `compare_reports`,
    `FindingComparison`, and `ComparisonResult`.
- **CLI `--compare PRIOR`.** Compares a single input report against a prior study
  file and prints the interval-change summary as JSON.

## [0.4.0] - 2026-07-01

### Added
- **De-identification (`Deidentifier`).** Rule-based PHI redaction so reports
  can be shared with collaborators or loaded into analytics pipelines. Detects
  dates, ages 90+, SSNs, medical-record and accession numbers, phone/fax
  numbers, emails, URLs, IP addresses, ZIP codes, and titled/labeled names.
  Every removal is recorded in an audit trail (`DeidentificationResult.redactions`)
  keyed to offsets in the original text, so the transformation is fully
  reproducible and reviewable — no ML, no external service.
  - Configurable: enable a subset of categories and override placeholder tokens.
  - Preserves clinical content — measurements such as "90 mm" are never mistaken
    for PHI because age matching requires an explicit age cue.
  - Convenience wrapper `deidentify(text, **kwargs)` and top-level exports of
    `Deidentifier`, `Redaction`, and `DeidentificationResult`.
- **CLI `--deidentify` / `-d`.** Scrubs PHI before parsing so downstream JSON,
  FHIR, and CSV output carry no identifiers; prints a per-file redaction summary
  to stderr.

## [0.3.1] - 2026-06-15

### Fixed
- **Critical-findings safety fix (false negatives).** When a term appeared more
  than once in a report, only the *first* occurrence was kept. If that first
  mention was negated (e.g. "No pneumothorax at the apex") it suppressed a later
  *real* mention (e.g. "Large pneumothorax at the base"), silently dropping a
  true critical alert. A term is now reported as negated only when **every**
  occurrence is negated; any active mention is preferred and surfaced with its
  own context.
- **Negation scoping.** Negation detection no longer crosses sentence
  boundaries. A negation in a previous sentence ("No acute hemorrhage.") can no
  longer negate a finding in the current one ("Large subdural hematoma is
  present."). The look-back window is now bounded by both `NEGATION_WINDOW`
  characters and the start of the current sentence.

## [0.3.0]

- Added `RecommendationExtractor`, `to_flat_dict()`, and `--format csv` CLI mode.
- Fixed section-header false splits mid-sentence.

## [0.2.0]

- Added CLI (`radreport`), `parse_batch()`, and `to_json()`.
- Fixed PE abbreviation regex bug.
