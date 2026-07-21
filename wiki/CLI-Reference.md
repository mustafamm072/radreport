# CLI Reference

After `pip install radreport`, the `radreport` command handles single-file and
batch processing.

```bash
radreport report.txt                                   # parse → JSON
radreport report.txt --critical                        # + critical findings
radreport report.txt --critical --recommend            # + follow-up recs
radreport report.txt --fhir --patient-id pt-001 -m CT  # FHIR DiagnosticReport
radreport report.txt --deidentify --critical           # scrub PHI first
radreport current.txt --compare prior.txt -m CT         # interval change
radreport report.txt --template                        # completeness (auto template)
radreport report.txt --template ct_abdomen_pelvis      # completeness (named)
radreport --list-templates                             # list template keys
radreport reports/*.txt --critical -o batch.json       # batch → JSON array
radreport reports/*.txt --critical --recommend --format csv -o cohort.csv
```

## Flags

| Flag | Short | Description |
|------|-------|-------------|
| `--modality MOD` | `-m` | CT, MRI, XR, US, NM, PET … |
| `--critical` | `-c` | Run critical findings detection |
| `--recommend` | `-r` | Extract follow-up imaging recommendations |
| `--deidentify` | `-d` | Redact PHI before parsing |
| `--compare PRIOR` | | Compare input against a prior study; interval-change JSON |
| `--template [NAME]` | | Completeness vs a template; omit NAME to auto-select |
| `--list-templates` | | Print available template keys and exit |
| `--fhir` | `-f` | Export FHIR R4 DiagnosticReport (implies `--critical`) |
| `--patient-id ID` | | FHIR Patient resource ID (with `--fhir`) |
| `--format FMT` | `--fmt` | `json` (default) or `csv` |
| `--output FILE` | `-o` | Write to FILE instead of stdout |

## Output shapes

- **JSON, single file** → one object. **Multiple files** → a JSON array.
- Each JSON object includes `source_file`. With `--template`, a `template` block
  is added; with `--compare`, the output is the interval-change summary instead.
- **CSV** → one flat row per report (see `ParsedReport.to_flat_dict`). With
  `--template`, completeness columns are appended.
- Diagnostics (de-id summaries, per-file errors, "Written to …") go to **stderr**,
  so stdout stays clean for piping.

## Notes & incompatibilities

- `--format csv` is **not** compatible with `--fhir`.
- `--compare` requires exactly one input FILE (the current study).
- An unknown `--template` key is rejected with the list of valid keys.

See also: [Report Templates](Report-Templates), [Interval Change](Interval-Change),
[De-identification](De-identification).
