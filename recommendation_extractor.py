"""
Follow-up recommendation extractor for radiology reports.

Extracts structured follow-up imaging recommendations from impression and
recommendation sections. Rule-based, zero-dependency, fully auditable.

IMPORTANT: Extracted recommendations are decision-support aids only.
Clinical judgement governs actual follow-up scheduling.
"""

import re
from typing import Optional
from .report_schema import ParsedReport, FollowUpRecommendation


# Sentence must contain one of these to be considered a recommendation
_TRIGGER = re.compile(
    r'\b(follow[- ]?up|surveillance|repeat\s+(?:CT|CTA|CTPA|MRI|MRA|ultrasound|US|'
    r'X-ray|XR|scan|imaging|study|mammograph))\b',
    re.IGNORECASE,
)

# Skip sentences that negate a follow-up
_NEGATIONS = [
    re.compile(r'\bno\s+(?:further\s+|additional\s+)?follow[- ]?up\b', re.IGNORECASE),
    re.compile(r'\bno\s+(?:further\s+|additional\s+)?imaging\b', re.IGNORECASE),
    re.compile(r'\bnot\s+(?:required|needed|indicated|recommended|necessary)\b', re.IGNORECASE),
    re.compile(r'\bno\s+repeat\b', re.IGNORECASE),
]

_URGENCY = re.compile(
    r'\b(urgent|emergent|immediately|stat|asap|as\s+soon\s+as\s+possible)\b',
    re.IGNORECASE,
)

# Imaging modality — order matters: more specific patterns first
_MODALITY_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r'\bCT(?:PA|A)?\b'),                                        "CT"),
    (re.compile(r'\bMR(?:I|A)?\b'),                                         "MRI"),
    (re.compile(r'\bPET(?:\s*[/\-]\s*CT)?\b'),                              "PET"),
    (re.compile(r'\bmammograph', re.IGNORECASE),                             "mammography"),
    (re.compile(r'\bultrasound\b|\bsonograph|\bsonogram\b', re.IGNORECASE),  "US"),
    (re.compile(r'\bUS\b'),                                                  "US"),
    (re.compile(r'\bX-ray\b|\bXR\b|\bradiograph', re.IGNORECASE),           "XR"),
    (re.compile(r'\bnuclear\s+medicine\b|\bNM\b'),                           "NM"),
]


def _extract_interval(text: str) -> Optional[str]:
    m = re.search(
        r'\b(\d+)[- ]?(year|years|month|months|week|weeks|day|days)\b',
        text,
        re.IGNORECASE,
    )
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower().rstrip('s')
        return f"{n} {unit}{'s' if n != 1 else ''}"
    if re.search(r'\bannual(?:ly)?\b|\byearly\b', text, re.IGNORECASE):
        return "annual"
    if re.search(r'\bbiannual\b|\bsemi[- ]annual\b', text, re.IGNORECASE):
        return "biannual"
    if re.search(r'\bshort[- ]term\b', text, re.IGNORECASE):
        return "short-term"
    return None


def _extract_modality(text: str) -> Optional[str]:
    for pattern, normalized in _MODALITY_RULES:
        if pattern.search(text):
            return normalized
    return None


def _is_negated(sentence: str) -> bool:
    return any(p.search(sentence) for p in _NEGATIONS)


class RecommendationExtractor:
    """
    Scans a ParsedReport for follow-up imaging recommendations.

    Usage:
        extractor = RecommendationExtractor()
        report = extractor.extract(parsed_report)
        for rec in report.recommendations:
            print(rec.interval, rec.modality, rec.urgency)
    """

    def extract(self, report: ParsedReport) -> ParsedReport:
        """
        Populate report.recommendations from recommendation and impression sections.
        Modifies the report in place and returns it.

        Args:
            report: A ParsedReport from ReportParser.parse()

        Returns:
            The same ParsedReport with recommendations populated.
        """
        target_sections = {"recommendation", "impression"}
        sentences: list[str] = []

        for section in report.sections:
            if section.name in target_sections:
                for sent in re.split(r'(?<=[.!?])\s+|\n', section.raw_text):
                    sent = sent.strip()
                    if sent:
                        sentences.append(sent)

        seen: set[str] = set()
        recommendations: list[FollowUpRecommendation] = []

        for sentence in sentences:
            if not _TRIGGER.search(sentence):
                continue
            if _is_negated(sentence):
                continue

            key = sentence.lower()
            if key in seen:
                continue
            seen.add(key)

            recommendations.append(FollowUpRecommendation(
                text=sentence,
                interval=_extract_interval(sentence),
                modality=_extract_modality(sentence),
                urgency="urgent" if _URGENCY.search(sentence) else "routine",
            ))

        report.recommendations = recommendations
        return report
