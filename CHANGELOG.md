# Changelog

All notable changes to this project are documented here.

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
