# Known Issues & Limitations

radreport is a **rule-based** library. That is a deliberate design choice — every
decision is traceable, there are no model weights, no GPU, and no external calls,
which is what makes it auditable and easy to clear through hospital IT review. The
trade-off is that rules do not generalize the way a language model does. This
document is an honest inventory of where the current rules fall short, so you can
decide where a human must stay in the loop.

> **Not a medical device.** Nothing here is intended for autonomous clinical
> decision-making. Every module is decision support for a human reviewer.

---

## Parsing

- **Header-driven sectioning.** Sections are detected from line-anchored header
  keywords (`FINDINGS:`, `IMPRESSION:`, …). Reports with no headers fall back to
  treating the whole text as findings. Unusual or institution-specific headers
  may not be recognized until added to `SECTION_PATTERNS`.
- **Measurement units.** Only `mm`, `cm`, and `in` are normalized. Volumes
  (`cc`, `mL`), areas (`cm²`), and Hounsfield units are not extracted as
  measurements. Ranges (`2–3 cm`) capture only the matched number(s), not the
  range semantics.
- **Anatomy tagging is first-match.** A finding sentence is tagged with the first
  anatomy keyword it contains, from a fixed list. A sentence spanning two organs
  is tagged with only one, and organs outside the keyword list are untagged.
- **Sentence splitting** is regex-based (`.!?`/newlines). Abbreviations with
  periods (e.g. "1.2 cm", "T8-T9") are largely handled, but exotic punctuation
  can still mis-split.

## Critical Findings Detection

- **Fixed vocabulary.** Detection is limited to the terms in `CRITICAL_TERMS`
  (45+ entries). Synonyms, misspellings, and terms outside the list are not
  flagged. The list is extensible at runtime.
- **Negation is lexical and sentence-scoped.** It catches common cues ("no",
  "without", "negative for", …) within the current sentence. It does **not**
  model complex or double negation ("cannot exclude", "not without"), hedging
  ("possibly", "cannot rule out"), or negation that spans clauses within one long
  sentence. When in doubt the detector fails *safe* — an active mention anywhere
  wins over a negated one — which can over-alert rather than under-alert.
- **No severity context.** Severity is attached to the term, not the described
  size/acuity. A "tiny" and a "large" pneumothorax carry the same severity label.

## Interval Change (Prior Comparison)

- **Measurable findings only.** Only findings that carry an extractable
  measurement are tracked. Purely qualitative change ("more confluent
  opacities") is out of scope because it cannot be matched reliably from text.
- **Text-based matching.** Findings are paired across studies by anatomy +
  token overlap, greedily and one-to-one. Two similar lesions in the same organ
  can be mismatched; re-worded descriptions of the same lesion can fail to match
  and be reported as `resolved` + `new`. Inspect `match_score` when auditing.
- **Generic thresholds.** The default 2 mm / 20% change thresholds are loosely
  RECIST/Fleischner-inspired, **not** a certified implementation of any society
  guideline. Tune them for your workflow.
- **Largest-dimension only.** Change is judged on the single largest dimension,
  not volumetric or sum-of-diameters (true RECIST) criteria.

## Report Templates & Completeness

- **Coverage is a textual signal.** An item is "covered" if one of its keywords
  appears in the findings/impression — it does **not** verify the structure was
  evaluated *correctly*, only that it was mentioned. A boilerplate "the visualized
  structures are unremarkable" may leave individual organs uncovered even though
  the study was adequate.
- **Keyword recall.** Coverage depends on the synonyms in each `TemplateItem`.
  Institution-specific phrasing may be missed until added. False "missing" is
  more likely than false "covered".
- **Auto-classification is heuristic.** Template selection uses modality +
  body-region keywords. An ambiguous or mislabeled report can be routed to the
  wrong template; check `classification_score` and prefer an explicit
  `template=` key when the study type is known.
- **Small built-in library.** Five study types ship today. Others require a
  custom `ReportTemplate` (see the README).

## De-identification

- **Not a HIPAA Safe Harbor guarantee.** Rule-based redaction is a strong first
  pass, not certified compliance. **Always review output before PHI leaves a
  controlled environment.**
- **Free-narrative names are not caught.** Names are matched only when they carry
  a title (`Dr. Smith`) or a header label (`Patient Name:`). A bare name in prose
  ("discussed with Johnson") is missed.
- **Text only.** PHI burned into images, embedded in DICOM tags, or present in
  non-text attachments is entirely out of scope — this operates on report text.
- **Locale.** Date, phone, ZIP, and SSN patterns are tuned to US formats.

## FHIR Export

- Emits a `DiagnosticReport` with contained `Observation`s for active critical
  findings. `ImagingStudy`, `Condition`, and body-site-coded observations are on
  the roadmap, not yet implemented.
- Uses **unspecified-body-region** LOINC codes per modality; it does not resolve
  the specific body-region LOINC for the study.
- Extension URLs use an `example.org` placeholder namespace; replace them with
  your own canonical URLs for production interoperability.

## General

- **English only.** All keyword lists and patterns are English-language.
- **Python 3.9+**, standard library only. No optional acceleration.

---

Found something not listed here? Please open an issue:
<https://github.com/mustafamm072/radreport/issues>.
