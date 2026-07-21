# Report Templates & Completeness

A report of a given study type is expected to address a known set of anatomic
structures. A chest radiograph should comment on the lungs, pleura, heart,
mediastinum, and bones; a CT abdomen/pelvis should cover the solid organs, bowel,
and vasculature. Structured-reporting initiatives (RSNA RadReport, ACR templates)
formalize these checklists so nothing important is silently omitted.

`TemplateMatcher` brings that idea to free text. It (1) picks the best-fit
template for a report and (2) checks, item by item, whether each expected
structure was actually addressed — producing a per-item result and an overall
**completeness** score.

## Quick start

```python
from radreport import match_template

match = match_template(report_text, modality="CT")   # template="auto"

match.template_key                       # "ct_abdomen_pelvis"
match.completeness                       # 0.85  (fraction of REQUIRED items covered)
[i.key for i in match.missing_items]     # ["pancreas"]
[i.key for i in match.covered_items]     # ["liver", "spleen", ...]
match.is_complete                        # False
```

From a parsed report, or with an explicit template:

```python
from radreport import ReportParser, TemplateMatcher

report  = ReportParser().parse(report_text, modality="CT")
matcher = TemplateMatcher()

matcher.classify(report)                       # "ct_chest"  (best-fit key, or None)
match = matcher.match(report, template="ct_chest")
matcher.available                              # list of template keys
```

## Built-in templates

| Key | Study type |
|-----|------------|
| `chest_xr` | Chest Radiograph |
| `ct_chest` | CT Chest |
| `ct_abdomen_pelvis` | CT Abdomen and Pelvis |
| `ct_head` | CT Head (non-contrast) |
| `mri_brain` | MRI Brain |

## How it works

**Auto-selection.** Each template scores by modality agreement (up to 1.0) plus
the fraction of its body-region keywords found in the report. The highest scorer
wins; ties break toward registry order. `match.classification_score` records the
confidence. Pass an explicit `template=` key to skip classification entirely.

**Coverage.** Checked only against the **findings + impression** (and preamble)
text — never the indication/technique — so a structure named in the clinical
history alone does not count as "addressed". Each item matches on word-boundary
keywords; the first matching keyword is recorded in `matched_keyword` for a fully
auditable decision.

**Completeness.** The fraction of *required* items that were covered.
`required=False` items (e.g. contrast enhancement, incidental free fluid) never
count against the score when absent — they appear in `items` but not in
`missing_items`.

## Result objects

`TemplateMatch`:

| Member | Meaning |
|--------|---------|
| `template_key`, `template_name` | Which template was applied |
| `auto_selected` | `True` if chosen by `classify`, `False` if named |
| `classification_score` | Auto-selection confidence (`None` when named) |
| `items` | list of `TemplateItemResult` |
| `covered_items` / `missing_items` | covered; required-and-uncovered |
| `completeness` | float in `[0, 1]` |
| `is_complete` | `True` when nothing required is missing |
| `to_dict()` / `to_flat_dict()` | serialization |

`TemplateItemResult`: `key`, `label`, `covered`, `required`, `matched_keyword`.

## Custom templates

```python
from radreport import TemplateMatcher, ReportTemplate, TemplateItem, TEMPLATES

mammo = ReportTemplate(
    key="mammography",
    name="Screening Mammography",
    modalities=("MG", "XR"),
    classifier_keywords=("breast", "mammograph", "calcification"),
    items=(
        TemplateItem("masses", "Masses", ("mass", "masses", "nodule")),
        TemplateItem("calcifications", "Calcifications", ("calcification", "calcifications")),
        TemplateItem("density", "Breast density", ("density", "dense")),
        TemplateItem("birads", "BI-RADS", ("bi-rads", "birads"), required=False),
    ),
)

# Extend the built-ins WITHOUT mutating the global registry:
matcher = TemplateMatcher(templates={**TEMPLATES, "mammography": mammo})
```

`TemplateItem(key, label, keywords, required=True)` — `keywords` is a tuple of
case-insensitive substrings matched on word boundaries.

## CLI

```bash
radreport report.txt --template                    # auto-select
radreport report.txt --template ct_abdomen_pelvis  # named
radreport report.txt --template --format csv       # adds completeness columns
radreport --list-templates
```

## Caveats

Completeness is a **textual** signal: it reflects whether a structure was
*mentioned*, not whether it was evaluated correctly. Boilerplate ("visualized
structures unremarkable") can leave individual organs uncovered. Treat low
completeness as a prompt for human review, not a defect verdict. See
[Known Issues](Known-Issues).
