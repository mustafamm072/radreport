# FAQ

### Why rule-based instead of ML?

Auditability and deployability. Every flag, redaction, and classification is
traceable to a specific rule — no model weights, no probabilistic output. With
zero dependencies and no external calls, it passes hospital IT/security review
and runs anywhere Python 3.9+ runs. The trade-off is that rules don't generalize
like a language model; see [Known Issues](Known-Issues).

### Does it send my data anywhere?

No. Everything runs locally in-process. There are no network calls in any module.

### Can I use it commercially?

Yes — MIT licensed. It is a developer tool, **not** a medical device, and is not
cleared for autonomous clinical decision-making. Keep a human in the loop.

### It didn't detect a section / finding / organ. Why?

The library matches fixed keyword lists and patterns. Institution-specific
headers, synonyms, and phrasing may not be recognized until added. Most lists are
extensible at runtime (`SECTION_PATTERNS`, `CRITICAL_TERMS`, custom
`ReportTemplate`s).

### Is de-identification HIPAA-compliant?

It is a strong rule-based first pass, not a compliance guarantee. Bare names in
free narrative and PHI inside images/DICOM tags are not caught. Always review
output before PHI leaves a controlled environment.

### How do I process a whole folder?

CLI: `radreport reports/*.txt --critical --format csv -o cohort.csv`.
API: `ReportParser().parse_batch(list_of_texts, modality="CT")`.

### How do I turn output into a DataFrame?

Use `to_flat_dict()` per report (one row each) and hand the list to
`pandas.DataFrame(...)`. The CLI's `--format csv` does the same from the shell.

### Which Python versions are supported?

3.9 through 3.12, standard library only.

### How do I cite it?

See [`CITATION.cff`](https://github.com/mustafamm072/radreport/blob/main/CITATION.cff)
and the DOI badge in the README.
