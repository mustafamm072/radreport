"""
Structured report templates and completeness checking.

A radiology report of a given study type is expected to address a known set of
anatomic structures — a chest radiograph should comment on the lungs, pleura,
heart, mediastinum, and bones; a CT abdomen/pelvis should cover the solid
organs, bowel, and vasculature; and so on. Structured-reporting initiatives
(e.g. RSNA RadReport, the ACR's structured templates) formalize these
checklists so nothing important goes unmentioned.

`TemplateMatcher` brings that idea to free text. Given a parsed report it:

  1. picks the best-fit template for the study (by modality + body-region
     keywords), or uses a template you name explicitly; and
  2. checks, item by item, whether the report actually addressed each expected
     structure, producing a per-item `covered`/`missing` result and an overall
     `completeness` score.

Like everything else in radreport this is rule-based, zero-dependency, and
fully auditable — every coverage decision records the exact keyword that matched
(or notes that nothing did). No ML, no external service.

Typical uses:
  * QA — flag reports that omitted an expected organ before sign-off.
  * Research — validate that a cohort's reports are structurally comparable.
  * Analytics — turn narrative reports into a completeness matrix.

IMPORTANT: Completeness here is a *textual* signal — it reflects whether a
structure was mentioned, not whether it was evaluated correctly. It assists
review workflows; it does not judge diagnostic quality.
"""

import re
from dataclasses import dataclass
from typing import Optional

from .report_schema import ParsedReport, TemplateItemResult, TemplateMatch


@dataclass(frozen=True)
class TemplateItem:
    """
    One checklist element a complete report of this type should address.

    `keywords` are matched case-insensitively against the report's findings and
    impression text on word boundaries. `required=False` marks an item as
    optional (present in some studies, e.g. contrast enhancement), so it does
    not count against the completeness score when absent.
    """
    key: str
    label: str
    keywords: tuple[str, ...]
    required: bool = True


@dataclass(frozen=True)
class ReportTemplate:
    """
    A structured template for a study type: its expected checklist items plus
    the metadata used to auto-classify a report to it.

    `modalities` and `classifier_keywords` are used only for auto-selection;
    `items` are the completeness checklist.
    """
    key: str
    name: str
    modalities: tuple[str, ...]
    classifier_keywords: tuple[str, ...]
    items: tuple[TemplateItem, ...]


# ---------------------------------------------------------------------------
# Built-in templates for common study types.
# Keyword lists favour recall — a structure counts as "addressed" if any of its
# common synonyms appears. They are intentionally editable (see register()).
# ---------------------------------------------------------------------------

_CHEST_XR = ReportTemplate(
    key="chest_xr",
    name="Chest Radiograph",
    modalities=("XR", "CR", "DX"),
    classifier_keywords=("chest", "lung", "lungs", "cardiac silhouette", "costophrenic"),
    items=(
        TemplateItem("lungs", "Lungs", ("lung", "lungs", "pulmonary", "parenchyma")),
        TemplateItem("pleura", "Pleura", ("pleura", "pleural", "effusion", "pneumothorax")),
        TemplateItem("heart", "Cardiac silhouette", ("heart", "cardiac", "cardiomediastinal", "cardiac silhouette")),
        TemplateItem("mediastinum", "Mediastinum / hila", ("mediastinum", "mediastinal", "hila", "hilar")),
        TemplateItem("bones", "Osseous structures", ("bone", "bones", "osseous", "rib", "ribs", "spine")),
        TemplateItem("soft_tissues", "Soft tissues", ("soft tissue", "soft tissues", "subcutaneous")),
        TemplateItem("devices", "Lines / tubes / devices", ("tube", "line", "catheter", "pacemaker", "device"), required=False),
    ),
)

_CT_CHEST = ReportTemplate(
    key="ct_chest",
    name="CT Chest",
    modalities=("CT", "CTA", "PETCT"),
    classifier_keywords=("chest", "thorax", "lung", "lungs", "mediastinum", "pulmonary nodule"),
    items=(
        TemplateItem("lungs", "Lungs / parenchyma", ("lung", "lungs", "parenchyma", "nodule", "nodules")),
        TemplateItem("airways", "Airways", ("airway", "airways", "bronchus", "bronchi", "trachea", "bronchial")),
        TemplateItem("pleura", "Pleura", ("pleura", "pleural", "effusion", "pneumothorax")),
        TemplateItem("mediastinum", "Mediastinum", ("mediastinum", "mediastinal")),
        TemplateItem("heart", "Heart / pericardium", ("heart", "cardiac", "pericardium", "pericardial")),
        TemplateItem("vessels", "Great vessels", ("aorta", "aortic", "pulmonary artery", "vascular", "vessel", "vessels")),
        TemplateItem("lymph_nodes", "Lymph nodes", ("lymph node", "lymph nodes", "lymphadenopathy", "nodal")),
        TemplateItem("chest_wall", "Chest wall / bones", ("chest wall", "bone", "bones", "osseous", "rib", "ribs")),
        TemplateItem("upper_abdomen", "Upper abdomen", ("liver", "adrenal", "upper abdomen"), required=False),
    ),
)

_CT_ABDOMEN_PELVIS = ReportTemplate(
    key="ct_abdomen_pelvis",
    name="CT Abdomen and Pelvis",
    modalities=("CT", "CTA", "PETCT"),
    classifier_keywords=("abdomen", "pelvis", "liver", "kidney", "kidneys", "bowel", "bladder"),
    items=(
        TemplateItem("liver", "Liver", ("liver", "hepatic")),
        TemplateItem("biliary", "Gallbladder / biliary", ("gallbladder", "biliary", "bile duct", "cholecyst")),
        TemplateItem("pancreas", "Pancreas", ("pancreas", "pancreatic")),
        TemplateItem("spleen", "Spleen", ("spleen", "splenic")),
        TemplateItem("adrenals", "Adrenal glands", ("adrenal", "adrenals")),
        TemplateItem("kidneys", "Kidneys / urinary", ("kidney", "kidneys", "renal", "ureter", "urinary")),
        TemplateItem("bowel", "Bowel", ("bowel", "colon", "small bowel", "intestine", "intestinal")),
        TemplateItem("appendix", "Appendix", ("appendix", "appendiceal"), required=False),
        TemplateItem("bladder", "Bladder", ("bladder", "vesical")),
        TemplateItem("pelvic_organs", "Pelvic organs", ("uterus", "ovary", "ovaries", "prostate", "adnexa"), required=False),
        TemplateItem("vasculature", "Vasculature", ("aorta", "aortic", "vascular", "vessel", "vessels", "iliac")),
        TemplateItem("lymph_nodes", "Lymph nodes", ("lymph node", "lymph nodes", "lymphadenopathy", "nodal")),
        TemplateItem("bones", "Osseous structures", ("bone", "bones", "osseous", "spine", "vertebra", "vertebral")),
        TemplateItem("free_fluid", "Free fluid / air", ("free fluid", "ascites", "free air", "pneumoperitoneum"), required=False),
    ),
)

_CT_HEAD = ReportTemplate(
    key="ct_head",
    name="CT Head (non-contrast)",
    modalities=("CT",),
    classifier_keywords=("head", "brain", "intracranial", "ventricles", "hemorrhage", "cerebral"),
    items=(
        TemplateItem("parenchyma", "Brain parenchyma", ("parenchyma", "brain", "cerebral", "gray-white", "gray white")),
        TemplateItem("ventricles", "Ventricles", ("ventricle", "ventricles", "ventricular")),
        TemplateItem("extra_axial", "Extra-axial spaces", ("extra-axial", "extra axial", "subdural", "epidural", "subarachnoid", "hemorrhage")),
        TemplateItem("midline", "Midline / mass effect", ("midline", "mass effect", "herniation")),
        TemplateItem("cisterns", "Basal cisterns", ("cistern", "cisterns"), required=False),
        TemplateItem("bones", "Calvarium / skull base", ("calvarium", "skull", "osseous", "bone", "bones", "fracture")),
        TemplateItem("sinuses", "Paranasal sinuses / mastoids", ("sinus", "sinuses", "mastoid", "mastoids"), required=False),
    ),
)

_MRI_BRAIN = ReportTemplate(
    key="mri_brain",
    name="MRI Brain",
    modalities=("MRI", "MR"),
    classifier_keywords=("brain", "cerebral", "white matter", "flair", "diffusion", "ventricles"),
    items=(
        TemplateItem("parenchyma", "Brain parenchyma", ("parenchyma", "white matter", "gray matter", "cerebral", "cortex", "cortical")),
        TemplateItem("ventricles", "Ventricles", ("ventricle", "ventricles", "ventricular")),
        TemplateItem("extra_axial", "Extra-axial spaces", ("extra-axial", "extra axial", "subdural", "epidural", "subarachnoid")),
        TemplateItem("posterior_fossa", "Posterior fossa / brainstem", ("posterior fossa", "brainstem", "brain stem", "cerebellum", "cerebellar")),
        TemplateItem("vessels", "Vasculature / flow voids", ("flow void", "flow voids", "vascular", "vessel", "vessels", "artery", "arteries")),
        TemplateItem("sella", "Sella / pituitary", ("sella", "sellar", "pituitary"), required=False),
        TemplateItem("orbits", "Orbits", ("orbit", "orbits", "orbital"), required=False),
        TemplateItem("sinuses", "Paranasal sinuses / mastoids", ("sinus", "sinuses", "mastoid", "mastoids"), required=False),
        TemplateItem("diffusion", "Diffusion", ("diffusion", "dwi", "restricted diffusion", "adc")),
        TemplateItem("enhancement", "Enhancement", ("enhancement", "enhancing", "contrast"), required=False),
    ),
)

# Registry of built-in templates, keyed by template key.
TEMPLATES: dict[str, ReportTemplate] = {
    t.key: t
    for t in (_CHEST_XR, _CT_CHEST, _CT_ABDOMEN_PELVIS, _CT_HEAD, _MRI_BRAIN)
}


def _coverage_text(report: ParsedReport) -> str:
    """
    The text used for completeness checking: the clinically descriptive
    sections (findings, impression, preamble). Falls back to the full report
    when no structured sections were detected. The indication/technique are
    intentionally excluded so a structure named only in the clinical history
    does not count as "addressed" in the findings.
    """
    target = {"findings", "impression", "preamble"}
    parts = [s.raw_text for s in report.sections if s.name in target]
    return ("\n".join(parts) if parts else report.raw_text).lower()


def _find_keyword(text_lower: str, keywords: tuple[str, ...]) -> Optional[str]:
    """Return the first keyword present in `text_lower` on a word boundary."""
    for kw in keywords:
        if re.search(r"\b" + re.escape(kw.lower()) + r"\b", text_lower):
            return kw
    return None


class TemplateMatcher:
    """
    Assesses whether a report addressed the structures expected for its study
    type, using structured report templates.

    Usage:
        matcher = TemplateMatcher()

        # Auto-select the best-fit template:
        match = matcher.match(report)

        # Or name a template explicitly:
        match = matcher.match(report, template="ct_abdomen_pelvis")

        print(match.completeness)                       # e.g. 0.85
        print([i.key for i in match.missing_items])     # e.g. ["pancreas"]

    Args (constructor):
        templates: mapping of template key -> ReportTemplate. Defaults to the
                   built-in TEMPLATES registry. Pass your own to add or replace
                   templates without mutating the global registry.
    """

    def __init__(self, templates: Optional[dict] = None):
        self.templates = dict(templates) if templates is not None else dict(TEMPLATES)

    @property
    def available(self) -> list[str]:
        """Template keys this matcher can select from."""
        return list(self.templates.keys())

    def _score(self, template: ReportTemplate, report: ParsedReport, text_lower: str) -> float:
        """
        Confidence in [0, ~2] that `template` fits `report`. Modality agreement
        contributes up to 1.0; body-region keyword coverage the rest.
        """
        score = 0.0
        if report.modality and report.modality.upper() in template.modalities:
            score += 1.0
        kws = template.classifier_keywords
        if kws:
            hits = sum(1 for kw in kws if _find_keyword(text_lower, (kw,)))
            score += hits / len(kws)
        return score

    def classify(self, report: ParsedReport) -> Optional[str]:
        """
        Return the key of the best-fit template for `report`, or None if there
        are no templates or nothing scores above zero. Ties break toward the
        registry order (i.e. the first template defined).
        """
        text_lower = _coverage_text(report)
        best_key, best_score = None, 0.0
        for key, tmpl in self.templates.items():
            s = self._score(tmpl, report, text_lower)
            if s > best_score:
                best_key, best_score = key, s
        return best_key

    def match(self, report: ParsedReport, template: str = "auto") -> TemplateMatch:
        """
        Check `report` for completeness against a template.

        Args:
            report:   A ParsedReport from ReportParser.parse().
            template: "auto" (default) to auto-select the best-fit template, or
                      an explicit template key (see `.available`).

        Returns:
            TemplateMatch with a per-item coverage result and a completeness
            score.

        Raises:
            ValueError: if an explicit template key is unknown, or if "auto" is
                        requested but no template can be selected.
        """
        text_lower = _coverage_text(report)

        if template == "auto":
            key = self.classify(report)
            if key is None:
                raise ValueError(
                    "Could not auto-select a template for this report. "
                    "Pass an explicit template key (see TemplateMatcher.available)."
                )
            auto_selected = True
            classification_score = round(self._score(self.templates[key], report, text_lower), 3)
        else:
            if template not in self.templates:
                raise ValueError(
                    f"Unknown template {template!r}. "
                    f"Available: {', '.join(self.templates)}"
                )
            key = template
            auto_selected = False
            classification_score = None

        tmpl = self.templates[key]
        items = []
        for it in tmpl.items:
            matched = _find_keyword(text_lower, it.keywords)
            items.append(TemplateItemResult(
                key=it.key,
                label=it.label,
                covered=matched is not None,
                required=it.required,
                matched_keyword=matched,
            ))

        return TemplateMatch(
            template_key=tmpl.key,
            template_name=tmpl.name,
            auto_selected=auto_selected,
            items=items,
            classification_score=classification_score,
        )


def match_template(
    text: str,
    template: str = "auto",
    modality: Optional[str] = None,
    **matcher_kwargs,
) -> TemplateMatch:
    """
    Convenience wrapper: parse a raw report string and check its completeness
    against a template.

        match = match_template(report_text, template="ct_chest", modality="CT")

    Extra keyword arguments are forwarded to TemplateMatcher.
    """
    from .report_parser import ReportParser

    report = ReportParser().parse(text, modality=modality)
    return TemplateMatcher(**matcher_kwargs).match(report, template=template)
