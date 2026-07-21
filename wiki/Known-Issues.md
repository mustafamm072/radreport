# Known Issues & Limitations

radreport is **rule-based** by design — auditable, dependency-free, and easy to
clear through hospital IT. The trade-off is that rules don't generalize like a
language model. This is an honest inventory of where they fall short. The
canonical, always-current copy lives in
[`KNOWN_ISSUES.md`](https://github.com/mustafamm072/radreport/blob/main/KNOWN_ISSUES.md).

> **Not a medical device.** Every module is decision support for a human reviewer.

**Parsing** — header-driven sectioning (unusual headers unrecognized until
added); only mm/cm/in normalized (no cc/mL/HU, no ranges); first-match anatomy
tagging; regex sentence splitting.

**Critical findings** — fixed 45+ term vocabulary; lexical, sentence-scoped
negation that doesn't model hedging or double negation; severity is per-term, not
size/acuity-aware. Fails *safe* (over-alerts rather than suppresses).

**Interval change** — measurable findings only; text-based one-to-one matching
that can mismatch similar lesions or split a re-worded lesion into
resolved+new; generic (non-certified) 2 mm/20% thresholds; largest-dimension
only, not volumetric/true-RECIST.

**Report templates** — coverage is a *textual* signal (mentioned ≠ evaluated
correctly); depends on each item's keyword synonyms; heuristic auto-classification
(check `classification_score`, prefer explicit `template=`); only five built-in
study types.

**De-identification** — not a HIPAA Safe Harbor guarantee; bare names without a
title/label are missed; text only (no image/DICOM-tag PHI); US-format patterns.

**FHIR export** — `DiagnosticReport` + contained `Observation`s only
(`ImagingStudy`/`Condition` on the roadmap); unspecified-body-region LOINC codes;
`example.org` placeholder extension URLs.

**General** — English only; Python 3.9+, standard library only.

Found something not listed? Open an issue:
<https://github.com/mustafamm072/radreport/issues>.
