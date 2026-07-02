"""
Rule-based de-identification (PHI redaction) for radiology reports.

Removes Protected Health Information so that reports can be shared with research
collaborators, stored in analytics warehouses, or processed off-site. Every
decision is a traceable regular-expression rule — no ML, no GPU, no external
service — so the transformation can be audited line by line and re-run
deterministically. This is what makes it acceptable in environments where
sending text to a cloud NER API is not an option.

The categories map to the HIPAA Safe Harbor identifier list where they are
reliably matchable from text alone: dates, telephone/fax numbers, email
addresses, SSNs, medical-record and accession numbers, URLs, IP addresses, ZIP
codes, ages over 89, and names that follow an explicit title or header label.

IMPORTANT — read before relying on this for compliance:
    Free-text de-identification is inherently imperfect. Names that appear in
    narrative prose *without* a title or label (e.g. a surname mentioned mid
    sentence) are NOT caught by a rule-based system. Treat the output as a
    strong first pass that must still be reviewed before any PHI leaves a
    controlled environment. This tool does not certify Safe Harbor compliance.
"""

import re
from typing import Iterable, Optional

from .report_schema import DeidentificationResult, Redaction


# ---------------------------------------------------------------------------
# Replacement placeholders, one per category.
# ---------------------------------------------------------------------------
PLACEHOLDERS: dict[str, str] = {
    "date": "[DATE]",
    "age": "[AGE]",
    "ssn": "[SSN]",
    "mrn": "[MRN]",
    "accession": "[ACCESSION]",
    "phone": "[PHONE]",
    "email": "[EMAIL]",
    "url": "[URL]",
    "ipv4": "[IP]",
    "zip": "[ZIP]",
    "name": "[NAME]",
}

# All categories, in the order they are applied. Order is only a tie-breaker
# for overlapping matches (earlier categories win); non-overlapping matches are
# unaffected. More specific / higher-confidence patterns come first.
DEFAULT_CATEGORIES: tuple[str, ...] = (
    "ssn", "mrn", "accession", "phone", "email", "url", "ipv4",
    "date", "age", "zip", "name",
)


# ---------------------------------------------------------------------------
# Rules. Each category maps to a list of compiled patterns. The full match
# (group 0) is what gets redacted, so patterns use lookahead/label groups to
# anchor context without consuming text that must be kept.
# ---------------------------------------------------------------------------
_MONTHS = (
    r"Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?"
)

_RULES: dict[str, list[re.Pattern]] = {
    "ssn": [
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ],
    "mrn": [
        # "MRN: 12345678", "Medical Record Number 12345678", "MRN# 1234567"
        re.compile(
            r"\b(?:MRN|medical\s+record\s+(?:number|no|#))\s*[:#]?\s*[A-Z]?\d[\d-]{4,}\b",
            re.IGNORECASE,
        ),
    ],
    "accession": [
        # "Accession: A12345678", "Acc # 12345678", "Accession Number 12345678"
        re.compile(
            r"\b(?:accession(?:\s+(?:number|no|#))?|acc\s*#)\s*[:#]?\s*[A-Z]{0,3}\d[\d-]{4,}\b",
            re.IGNORECASE,
        ),
    ],
    "phone": [
        # (555) 123-4567 / 555-123-4567 / 555.123.4567 / +1 555 123 4567
        re.compile(
            r"(?<!\d)(?:\+?1[\s.-]?)?(?:\(\d{3}\)|\d{3})[\s.-]\d{3}[\s.-]\d{4}(?!\d)"
        ),
    ],
    "email": [
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ],
    "url": [
        re.compile(r"\bhttps?://[^\s<>\"')]+", re.IGNORECASE),
    ],
    "ipv4": [
        re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    ],
    "date": [
        # 03/10/2024, 3-10-24, 2024-03-10
        re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),
        re.compile(r"\b\d{4}-\d{1,2}-\d{1,2}\b"),
        # March 5, 2024 / 5 March 2024 / Mar 2024
        re.compile(rf"\b(?:{_MONTHS})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}\b", re.IGNORECASE),
        re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:{_MONTHS})\.?\s+\d{{4}}\b", re.IGNORECASE),
        re.compile(rf"\b(?:{_MONTHS})\.?\s+\d{{4}}\b", re.IGNORECASE),
    ],
    "age": [
        # HIPAA: ages 90+ must not be reported in the clear. Require an age cue
        # so ordinary measurements ("90 mm") are never mistaken for an age.
        re.compile(
            r"\b(?:9\d|1\d\d)\s*[- ]?\s*(?:years?|yrs?|y)[- ]?(?:old|/o|o)\b",
            re.IGNORECASE,
        ),
        re.compile(r"\bage[d]?\s*[:#]?\s*(?:9\d|1\d\d)\b", re.IGNORECASE),
    ],
    "zip": [
        # Only when preceded by a 2-letter state code, to avoid nuking any 5-digit number.
        re.compile(r"\b[A-Z]{2}\s+\d{5}(?:-\d{4})?\b"),
    ],
    "name": [
        # Titled names: Dr. Jane Smith, Mr. John Q. Doe
        re.compile(
            r"\b(?:Dr|Doctor|Mr|Mrs|Ms|Miss|Prof)\.?\s+"
            r"[A-Z][a-z]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-z]+)?"
        ),
        # Header label followed by a value, e.g. "Patient Name: John Doe".
        # Only the value (group 1) is redacted; the label is preserved. The
        # value stops at a column break (2+ spaces) or end of line so that a
        # multi-field header line ("Name: Doe    MRN: 123") does not swallow the
        # following fields — those are matched by their own category rules.
        re.compile(
            r"(?im)^[ \t]*(?:patient(?:\s+name)?|name|physician|"
            r"referring(?:\s+physician)?|referred\s+by|dictated\s+by|"
            r"signed\s+by|attending|resident|technologist)\s*:[ \t]*"
            r"([^\n]+?)(?=\s{2,}|$)"
        ),
    ],
}


class Deidentifier:
    """
    Redact PHI from radiology report text.

    Usage:
        deid = Deidentifier()
        result = deid.deidentify(raw_text)
        clean_text = result.text
        print(result.category_counts())   # {"date": 2, "mrn": 1, ...}

    Args:
        categories: Iterable of category names to enable. Defaults to all.
        placeholders: Optional overrides for the replacement tokens, e.g.
                      {"name": "XXXX"}. Categories not listed keep their default.
    """

    def __init__(
        self,
        categories: Optional[Iterable[str]] = None,
        placeholders: Optional[dict[str, str]] = None,
    ):
        requested = tuple(categories) if categories is not None else DEFAULT_CATEGORIES
        unknown = [c for c in requested if c not in _RULES]
        if unknown:
            raise ValueError(
                f"Unknown de-identification categor{'y' if len(unknown) == 1 else 'ies'}: "
                f"{', '.join(unknown)}. Valid options: {', '.join(sorted(_RULES))}."
            )
        # Preserve the canonical ordering (tie-break priority) among requested cats.
        self.categories = tuple(c for c in DEFAULT_CATEGORIES if c in set(requested))
        self.placeholders = {**PLACEHOLDERS, **(placeholders or {})}

    def deidentify(self, text: str) -> DeidentificationResult:
        """
        Scrub PHI from `text` and return a DeidentificationResult.

        The returned `text` has every detected identifier replaced by a category
        placeholder. `redactions` is the audit trail, ordered by position, with
        offsets into the ORIGINAL text.
        """
        if text is None:
            raise ValueError("Text cannot be None.")

        candidates: list[tuple[int, int, str]] = []  # (start, end, category)
        for category in self.categories:
            for pattern in _RULES[category]:
                for m in pattern.finditer(text):
                    # If the pattern captured a value group (label fields), redact
                    # only that group; otherwise redact the whole match.
                    if m.groups():
                        start, end = m.span(1)
                    else:
                        start, end = m.span(0)
                    if start < end:
                        candidates.append((start, end, category))

        # Resolve overlaps: sort by start, then longer span, then category priority.
        priority = {c: i for i, c in enumerate(self.categories)}
        candidates.sort(key=lambda c: (c[0], -(c[1] - c[0]), priority.get(c[2], 99)))

        chosen: list[tuple[int, int, str]] = []
        last_end = 0
        for start, end, category in candidates:
            if start >= last_end:
                chosen.append((start, end, category))
                last_end = end

        # Rebuild the scrubbed text and the redaction records in one pass.
        out_parts: list[str] = []
        redactions: list[Redaction] = []
        cursor = 0
        for start, end, category in chosen:
            out_parts.append(text[cursor:start])
            replacement = self.placeholders[category]
            out_parts.append(replacement)
            redactions.append(Redaction(
                category=category,
                original=text[start:end],
                replacement=replacement,
                start=start,
                end=end,
            ))
            cursor = end
        out_parts.append(text[cursor:])

        return DeidentificationResult(text="".join(out_parts), redactions=redactions)

    @property
    def supported_categories(self) -> list[str]:
        """All PHI categories this de-identifier can detect."""
        return list(_RULES.keys())


def deidentify(text: str, **kwargs) -> DeidentificationResult:
    """Convenience wrapper: `Deidentifier(**kwargs).deidentify(text)`."""
    return Deidentifier(**kwargs).deidentify(text)
