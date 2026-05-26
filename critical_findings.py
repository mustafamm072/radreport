"""
Critical findings detector for radiology reports.

Rule-based and fully auditable — no ML, no external dependencies.
Designed to be safe to use in clinical alerting pipelines.

IMPORTANT: This library flags *potential* critical findings for human review.
It is NOT a substitute for radiologist interpretation.
"""

import re
from .report_schema import ParsedReport, CriticalFinding


# ---------------------------------------------------------------------------
# Critical findings dictionary
# Format: term -> (category, severity)
# severity levels: "critical" | "urgent" | "significant"
# ---------------------------------------------------------------------------

CRITICAL_TERMS: dict[str, tuple[str, str]] = {
    # Vascular emergencies
    "aortic dissection":            ("vascular", "critical"),
    "aortic rupture":               ("vascular", "critical"),
    "aortic aneurysm":              ("vascular", "urgent"),
    "pulmonary embolism":           ("pulmonary", "critical"),
    "pe":                           ("pulmonary", "critical"),  # abbreviation
    "saddle embolus":               ("pulmonary", "critical"),
    "deep vein thrombosis":         ("vascular", "urgent"),
    "dvt":                          ("vascular", "urgent"),
    "venous thrombosis":            ("vascular", "urgent"),

    # Pulmonary
    "pneumothorax":                 ("pulmonary", "critical"),
    "tension pneumothorax":         ("pulmonary", "critical"),
    "hemothorax":                   ("pulmonary", "critical"),
    "pneumomediastinum":            ("pulmonary", "urgent"),
    "airway obstruction":           ("pulmonary", "critical"),
    "pulmonary edema":              ("pulmonary", "urgent"),
    "consolidation":                ("pulmonary", "significant"),

    # Neurological
    "intracranial hemorrhage":      ("neuro", "critical"),
    "subdural hematoma":            ("neuro", "critical"),
    "subdural hemorrhage":          ("neuro", "critical"),
    "epidural hematoma":            ("neuro", "critical"),
    "subarachnoid hemorrhage":      ("neuro", "critical"),
    "cerebral infarction":          ("neuro", "critical"),
    "stroke":                       ("neuro", "critical"),
    "brain herniation":             ("neuro", "critical"),
    "midline shift":                ("neuro", "critical"),
    "hydrocephalus":                ("neuro", "urgent"),
    "mass effect":                  ("neuro", "urgent"),

    # Abdominal
    "bowel perforation":            ("abdominal", "critical"),
    "free air":                     ("abdominal", "critical"),
    "pneumoperitoneum":             ("abdominal", "critical"),
    "mesenteric ischemia":          ("abdominal", "critical"),
    "bowel obstruction":            ("abdominal", "urgent"),
    "intussusception":              ("abdominal", "urgent"),
    "appendicitis":                 ("abdominal", "urgent"),
    "ruptured ectopic":             ("abdominal", "critical"),
    "splenic laceration":           ("abdominal", "critical"),
    "hepatic laceration":           ("abdominal", "critical"),

    # Cardiac
    "pericardial effusion":         ("cardiac", "urgent"),
    "cardiac tamponade":            ("cardiac", "critical"),
    "myocardial infarction":        ("cardiac", "critical"),

    # Spinal / trauma
    "spinal cord compression":      ("spinal", "critical"),
    "cervical fracture":            ("spinal", "critical"),
    "unstable fracture":            ("spinal", "critical"),
    "cord compression":             ("spinal", "critical"),

    # Oncologic
    "malignancy":                   ("oncologic", "significant"),
    "metastasis":                   ("oncologic", "significant"),
    "metastases":                   ("oncologic", "significant"),
    "lymphoma":                     ("oncologic", "significant"),
    "carcinoma":                    ("oncologic", "significant"),
}

# Negation phrases — if a finding is preceded by these, mark as negated
NEGATION_PHRASES = [
    r"no\s+",
    r"no\s+evidence\s+of\s+",
    r"no\s+acute\s+",
    r"without\s+",
    r"absence\s+of\s+",
    r"negative\s+for\s+",
    r"unremarkable\s+for\s+",
    r"ruled\s+out",
    r"not\s+seen",
    r"not\s+identified",
    r"not\s+present",
]

NEGATION_WINDOW = 60  # characters to look back for negation context


def _is_negated(text: str, match_start: int) -> bool:
    """Check if a matched term is preceded by a negation phrase."""
    window_start = max(0, match_start - NEGATION_WINDOW)
    preceding = text[window_start:match_start].lower()

    for phrase in NEGATION_PHRASES:
        if re.search(phrase, preceding):
            return True
    return False


def _get_sentence_context(text: str, match_start: int, match_end: int) -> str:
    """Extract the sentence containing the matched term."""
    # Walk back to sentence start
    start = text.rfind('.', 0, match_start)
    start = start + 1 if start != -1 else 0

    # Walk forward to sentence end
    end = text.find('.', match_end)
    end = end + 1 if end != -1 else len(text)

    return text[start:end].strip()


class CriticalFindingsDetector:
    """
    Scans a ParsedReport for critical, urgent, and significant findings.

    Usage:
        detector = CriticalFindingsDetector()
        report = detector.detect(parsed_report)
        # report.critical_findings is now populated
    """

    def detect(self, report: ParsedReport) -> ParsedReport:
        """
        Scan all sections of a ParsedReport and attach CriticalFinding objects.
        Modifies the report in place and returns it.

        Args:
            report: A ParsedReport from ReportParser.parse()

        Returns:
            The same ParsedReport with critical_findings populated.
        """
        # Focus on clinically meaningful sections
        target_sections = {"findings", "impression", "preamble"}
        scan_text_parts = []

        for section in report.sections:
            if section.name in target_sections:
                scan_text_parts.append(section.raw_text)

        # Fallback: scan full text if no structured sections
        scan_text = "\n".join(scan_text_parts) if scan_text_parts else report.raw_text

        findings: list[CriticalFinding] = []
        seen_terms: set[str] = set()

        for term, (category, severity) in CRITICAL_TERMS.items():
            pattern = re.compile(r'\b' + re.escape(term) + r'\b', re.IGNORECASE)

            for match in pattern.finditer(scan_text):
                normalized_term = term.strip()
                if normalized_term in seen_terms:
                    continue
                seen_terms.add(normalized_term)

                negated = _is_negated(scan_text, match.start())
                context = _get_sentence_context(scan_text, match.start(), match.end())

                findings.append(CriticalFinding(
                    term=normalized_term,
                    category=category,
                    severity=severity,
                    context=context,
                    negated=negated,
                ))

        # Sort: critical first, then urgent, then significant; negated last
        severity_order = {"critical": 0, "urgent": 1, "significant": 2}
        findings.sort(key=lambda f: (f.negated, severity_order.get(f.severity, 9)))

        report.critical_findings = findings
        return report

    @property
    def supported_terms(self) -> list[str]:
        """Return all terms currently monitored."""
        return list(CRITICAL_TERMS.keys())
