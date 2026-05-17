"""
Core radiology report parser.
Extracts structured data from free-text radiology reports.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from .report_schema import (
    ParsedReport, ReportSection, Measurement, Finding
)


# Common section headers across radiology report styles
SECTION_PATTERNS = {
    "indication":       r"(?i)(indication|clinical\s+indication|reason\s+for\s+exam|history)[:\s]",
    "technique":        r"(?i)(technique|procedure|protocol|method)[:\s]",
    "comparison":       r"(?i)(comparison|prior\s+study|prior\s+exam|previous)[:\s]",
    "findings":         r"(?i)(findings?|observations?|result)[:\s]",
    "impression":       r"(?i)(impression|conclusion|summary|assessment|diagnosis)[:\s]",
    "recommendation":   r"(?i)(recommendation|follow[- ]?up|advised)[:\s]",
}

# Measurement normalization patterns
MEASUREMENT_PATTERNS = [
    # e.g. "1.2 x 0.8 x 0.5 cm", "12 x 8 mm"
    r"(\d+\.?\d*)\s*[xX×]\s*(\d+\.?\d*)\s*(?:[xX×]\s*(\d+\.?\d*)\s*)?(mm|cm|in)",
    # e.g. "1.2cm", "12mm", "1.2 cm"
    r"(\d+\.?\d*)\s*(mm|cm|in)\b",
]

# Anatomy subsection keywords for finding-level parsing
ANATOMY_KEYWORDS = [
    "lung", "lungs", "heart", "cardiac", "mediastinum", "pleura", "pleural",
    "liver", "spleen", "kidney", "kidneys", "pancreas", "adrenal", "gallbladder",
    "bowel", "colon", "appendix", "bladder", "uterus", "ovary", "prostate",
    "aorta", "vascular", "lymph", "lymphadenopathy",
    "brain", "cerebral", "ventricle", "sulci", "white matter", "posterior fossa",
    "spine", "vertebra", "disc", "cord", "canal",
    "bone", "osseous", "fracture", "joint",
    "soft tissue", "chest wall", "abdomen", "pelvis",
]


def _normalize_measurement(value: float, unit: str) -> float:
    """Normalize all measurements to millimeters."""
    unit = unit.lower()
    if unit == "cm":
        return round(value * 10, 2)
    if unit == "in":
        return round(value * 25.4, 2)
    return round(value, 2)


def _extract_measurements(text: str) -> list[Measurement]:
    """Extract and normalize all measurements from a text block."""
    measurements = []
    seen = set()

    for pattern in MEASUREMENT_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = match.groups()
            raw = match.group(0).strip()

            if raw in seen:
                continue
            seen.add(raw)

            unit = groups[-1].lower()

            if len(groups) == 2:
                # Single dimension — matches pattern 2: (value, unit)
                dim1 = float(groups[0])
                measurements.append(Measurement(
                    raw=raw,
                    dimensions_mm=[_normalize_measurement(dim1, unit)],
                    unit_original=unit,
                ))
            elif len(groups) == 4:
                # Two or three dimensions — matches pattern 1: (d1, d2, d3_or_None, unit)
                dim1, dim2 = float(groups[0]), float(groups[1])
                dim3 = float(groups[2]) if groups[2] else None
                dims = [
                    _normalize_measurement(dim1, unit),
                    _normalize_measurement(dim2, unit),
                ]
                if dim3:
                    dims.append(_normalize_measurement(dim3, unit))
                measurements.append(Measurement(
                    raw=raw,
                    dimensions_mm=dims,
                    unit_original=unit,
                ))

    return measurements


def _split_into_sections(text: str) -> dict[str, str]:
    """
    Split report text into labeled sections.
    Returns a dict of section_name -> raw text content.
    """
    # Find all section header positions
    hits = []
    for section_name, pattern in SECTION_PATTERNS.items():
        for match in re.finditer(pattern, text):
            hits.append((match.start(), match.end(), section_name))

    if not hits:
        # No sections detected — treat the whole thing as findings
        return {"findings": text.strip()}

    hits.sort(key=lambda x: x[0])

    sections = {}
    for i, (start, end, name) in enumerate(hits):
        next_start = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        content = text[end:next_start].strip()
        # If the same section appears twice, concatenate
        if name in sections:
            sections[name] = sections[name] + "\n" + content
        else:
            sections[name] = content

    # Capture any text before the first section header as preamble
    if hits[0][0] > 0:
        preamble = text[:hits[0][0]].strip()
        if preamble:
            sections["preamble"] = preamble

    return sections


def _extract_findings_from_section(text: str) -> list[Finding]:
    """
    Parse individual findings from a findings section.
    Groups sentences by anatomy keyword when possible.
    """
    findings = []
    sentences = re.split(r'(?<=[.!?])\s+|\n', text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        anatomy = None
        lower = sentence.lower()
        for kw in ANATOMY_KEYWORDS:
            if kw in lower:
                anatomy = kw
                break

        measurements = _extract_measurements(sentence)

        findings.append(Finding(
            text=sentence,
            anatomy=anatomy,
            measurements=measurements,
        ))

    return findings


class ReportParser:
    """
    Main parser class for radiology free-text reports.

    Usage:
        parser = ReportParser()
        result = parser.parse(report_text)
    """

    def parse(self, text: str, modality: Optional[str] = None) -> ParsedReport:
        """
        Parse a free-text radiology report into structured data.

        Args:
            text:     Raw report text (plain text or lightly formatted).
            modality: Optional hint — "CT", "MRI", "XR", "US", "NM", etc.

        Returns:
            ParsedReport dataclass with sections, findings, measurements.
        """
        if not text or not text.strip():
            raise ValueError("Report text cannot be empty.")

        raw_sections = _split_into_sections(text)

        sections: list[ReportSection] = []
        all_measurements: list[Measurement] = []

        for name, content in raw_sections.items():
            measurements = _extract_measurements(content)
            all_measurements.extend(measurements)

            findings = []
            if name in ("findings", "impression"):
                findings = _extract_findings_from_section(content)

            sections.append(ReportSection(
                name=name,
                raw_text=content,
                findings=findings,
                measurements=measurements,
            ))

        # Pull out impression text for convenience
        impression_text = raw_sections.get("impression", "")
        findings_text = raw_sections.get("findings", "")

        return ParsedReport(
            raw_text=text,
            modality=modality,
            sections=sections,
            impression=impression_text,
            findings_text=findings_text,
            all_measurements=all_measurements,
        )
