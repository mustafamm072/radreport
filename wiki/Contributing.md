# Contributing

Contributions are welcome — especially new keywords, section headers, templates,
and de-identification patterns drawn from real-world reports.

## Dev setup

```bash
git clone https://github.com/mustafamm072/radreport.git
cd radreport
pip install -e ".[dev]"
pytest -q
```

## Project conventions

- **Zero runtime dependencies.** The `dependencies` list in `pyproject.toml`
  stays empty. Standard library only. (`dev` extras may add test tooling.)
- **Rule-based & auditable.** No ML, no network calls, no non-determinism. Every
  decision must be explainable from a rule a reviewer can read.
- **Schemas live in `report_schema.py`** as dataclasses, each with a `to_dict()`.
  Adding a field with a default is fine; changing existing `to_dict()` /
  `to_flat_dict()` output is a breaking change — call it out.
- **New capability = new module + convenience wrapper + top-level export**,
  mirroring `Deidentifier` / `ReportComparator` / `TemplateMatcher`.
- **Every change ships with tests.** Add to `tests/test_radreport.py`.

## Adding a template

Define a `ReportTemplate` in `radreport/templates.py`, add it to the `TEMPLATES`
registry tuple, and add coverage/classification tests. Favour keyword *recall*
(include common synonyms) and mark genuinely optional structures `required=False`
so they don't penalize completeness. See [Report Templates](Report-Templates).

## Adding critical terms

Add to `CRITICAL_TERMS` in `radreport/critical_findings.py` as
`term → (category, severity)`, and add a detection + negation test.

## Pull requests

1. Branch from `main`.
2. `pytest -q` must be green.
3. Update the README, [CHANGELOG](https://github.com/mustafamm072/radreport/blob/main/CHANGELOG.md),
   and relevant wiki pages.
4. Note any user-visible or schema changes explicitly.

## Releasing

Bump the version in `pyproject.toml`, `radreport/__init__.py`, and
`CITATION.cff`; add a CHANGELOG entry; tag the release.
