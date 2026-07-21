# De-identification

`Deidentifier` strips Protected Health Information (PHI) from a report before it
leaves a controlled environment — for research collaboration, analytics, or
off-site processing. Rule-based and fully auditable: every removal is a traceable
regex match recorded with its original offset. No ML, no cloud NER.

```python
from radreport import Deidentifier

result = Deidentifier().deidentify(raw_text)

result.text               # scrubbed report, safe to share
result.redaction_count    # e.g. 11
result.category_counts()  # {"date": 3, "mrn": 1, "name": 2, ...}

for r in result.redactions:            # audit trail, keyed to ORIGINAL offsets
    print(r.category, r.original, "→", r.replacement, f"@{r.start}:{r.end}")
```

## What it detects

Categories map to the HIPAA Safe Harbor identifiers reliably matchable from text:

| Category | Examples |
|----------|----------|
| `date` | `03/10/2024`, `2024-03-10`, `March 5, 2024` |
| `age` | ages **90+** (`94-year-old`) |
| `ssn` | `123-45-6789` |
| `mrn` | `MRN: 12345678` |
| `accession` | `Accession: A98765432` |
| `phone` | `(555) 123-4567` |
| `email` | `jdoe@example.com` |
| `url` | `http://pacs.hospital.org/...` |
| `ipv4` | `10.0.0.1` |
| `zip` | `DC 20500` (ZIP after a state code) |
| `name` | titled (`Dr. Jane Smith`) and header fields (`Patient Name: …`) |

Clinical content is preserved: a `6 mm` nodule or `90 mm` mass is never mistaken
for PHI, because age matching requires an explicit age cue.

## Configuration

```python
Deidentifier(
    categories=["date", "name"],          # redact only these
    placeholders={"name": "XXXX"},        # custom token
)

from radreport import deidentify
deidentify(raw_text, categories=["date"])  # one-shot convenience wrapper
```

## CLI

```bash
radreport report.txt --deidentify --critical    # scrub, then parse/detect
```

> **Not a compliance guarantee.** Rule-based de-identification is a strong first
> pass, not certified HIPAA Safe Harbor. Bare names in free narrative (no title
> or label) are **not** caught, and PHI in images/DICOM tags is out of scope.
> Always review output before PHI leaves a controlled environment. See
> [Known Issues](Known-Issues).
