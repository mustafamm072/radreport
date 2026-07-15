"""
Interval-change detector: compares a current radiology report against a prior
study and classifies each trackable finding as new / increased / decreased /
stable / resolved.

This answers the single most common question asked of a follow-up study:
*is the lesion growing?* Tumor-response assessment (RECIST-style) and nodule
surveillance (Fleischner-style) both hinge on the interval change of a measured
lesion's largest dimension — and that is exactly what this module extracts.

Like everything else in radreport it is rule-based, zero-dependency, and fully
auditable: matching between studies is a transparent anatomy + token-overlap
score, and every comparison records the texts and measurements it was derived
from. No ML, no embeddings, no external service.

Scope: the comparator tracks *measurable* findings — findings that carry an
extractable measurement (nodules, masses, lymph nodes, effusions with a size).
Unmeasured qualitative statements are intentionally out of scope because they
cannot be matched reliably from text alone.

IMPORTANT: Interval-change classification is decision support for human review,
not a substitute for a radiologist directly comparing the images. Thresholds are
generic defaults, not a specific society guideline.
"""

import re
from typing import Optional

from .report_schema import ParsedReport, Finding, FindingComparison, ComparisonResult


# Default change thresholds for the largest dimension. A change is only called
# "increased"/"decreased" when it clears BOTH an absolute and a relative bar,
# which suppresses noise from measurement/rounding jitter on small lesions.
# These are deliberately generic (loosely RECIST/Fleischner-inspired), not a
# certified implementation of any one society guideline — override as needed.
DEFAULT_MIN_ABS_MM = 2.0     # absolute change in mm
DEFAULT_MIN_PCT = 20.0       # relative change in percent

# Minimum token-overlap score for two findings to be considered the same lesion.
DEFAULT_MIN_MATCH_SCORE = 0.18

# Tokens that carry no matching signal — measurements, units, and filler.
_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "at", "to",
    "and", "or", "with", "without", "there", "no", "seen", "noted", "measuring",
    "measures", "now", "previously", "prior", "which", "that", "this", "again",
    "mm", "cm", "in", "x", "by", "approximately", "approx", "about", "size",
    "sized", "left", "right",  # laterality handled separately via anatomy
}
_TOKEN_RE = re.compile(r"[a-z]+")
_NUMERIC_RE = re.compile(r"\d")


def _tokens(text: str) -> set[str]:
    """Content tokens of a finding sentence, minus stopwords and numerics."""
    out = set()
    for tok in _TOKEN_RE.findall(text.lower()):
        if tok in _STOPWORDS or _NUMERIC_RE.search(tok):
            continue
        out.add(tok)
    return out


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _trackable_findings(report: ParsedReport) -> list[Finding]:
    """
    Findings that carry a measurement, drawn from findings + impression sections.
    Deduplicated by text so a lesion repeated across sections is tracked once.
    """
    out: list[Finding] = []
    seen: set[str] = set()
    for section in report.sections:
        if section.name not in ("findings", "impression"):
            continue
        for f in section.findings:
            if not f.measurements:
                continue
            key = f.text.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(f)
    return out


def _largest_mm(finding: Finding) -> Optional[float]:
    dims = [m.largest_dimension_mm for m in finding.measurements if m.dimensions_mm]
    return max(dims) if dims else None


def _match_score(current: Finding, prior: Finding) -> float:
    """
    Similarity score in [0, 1] for whether two findings describe the same lesion.
    Anatomy agreement is a strong prior; token overlap does the rest.
    """
    score = _jaccard(_tokens(current.text), _tokens(prior.text))
    if current.anatomy and prior.anatomy:
        if current.anatomy == prior.anatomy:
            score += 0.25
        else:
            score -= 0.15
    return max(0.0, min(1.0, score))


class ReportComparator:
    """
    Compares a current ParsedReport against a prior one and classifies the
    interval change of every measurable finding.

    Usage:
        comparator = ReportComparator()
        result = comparator.compare(current_report, prior_report)
        for c in result.comparisons:
            print(c.status, c.anatomy, c.prior_mm, "->", c.current_mm)

    Args (constructor):
        min_abs_mm:      absolute mm change required to leave "stable"
        min_pct:         relative % change required to leave "stable"
        min_match_score: token-overlap threshold to pair two findings
    """

    def __init__(
        self,
        min_abs_mm: float = DEFAULT_MIN_ABS_MM,
        min_pct: float = DEFAULT_MIN_PCT,
        min_match_score: float = DEFAULT_MIN_MATCH_SCORE,
    ):
        self.min_abs_mm = min_abs_mm
        self.min_pct = min_pct
        self.min_match_score = min_match_score

    def _classify_change(self, current_mm: float, prior_mm: float) -> str:
        delta = current_mm - prior_mm
        pct = (delta / prior_mm * 100.0) if prior_mm else 0.0
        if abs(delta) >= self.min_abs_mm and abs(pct) >= self.min_pct:
            return "increased" if delta > 0 else "decreased"
        return "stable"

    def compare(
        self, current: ParsedReport, prior: ParsedReport
    ) -> ComparisonResult:
        """
        Compare `current` against `prior`. Returns a ComparisonResult with one
        FindingComparison per trackable finding on either side.

        Matching is greedy and one-to-one: the highest-scoring current/prior
        pairs above `min_match_score` are locked in first; leftovers on the
        current side become "new" and leftovers on the prior side "resolved".
        """
        cur_findings = _trackable_findings(current)
        pri_findings = _trackable_findings(prior)

        # Score every cross pair, then greedily accept best matches first.
        candidates = []
        for ci, cf in enumerate(cur_findings):
            for pi, pf in enumerate(pri_findings):
                s = _match_score(cf, pf)
                if s >= self.min_match_score:
                    candidates.append((s, ci, pi))
        candidates.sort(key=lambda t: t[0], reverse=True)

        matched_cur: dict[int, int] = {}   # ci -> pi
        matched_pri: set[int] = set()
        for s, ci, pi in candidates:
            if ci in matched_cur or pi in matched_pri:
                continue
            matched_cur[ci] = pi
            matched_pri.add(pi)

        comparisons: list[FindingComparison] = []

        # Matched pairs → increased / decreased / stable
        for ci, pi in sorted(matched_cur.items()):
            cf, pf = cur_findings[ci], pri_findings[pi]
            cur_mm, pri_mm = _largest_mm(cf), _largest_mm(pf)
            delta = round(cur_mm - pri_mm, 2)
            pct = round((delta / pri_mm * 100.0), 1) if pri_mm else None
            comparisons.append(FindingComparison(
                status=self._classify_change(cur_mm, pri_mm),
                anatomy=cf.anatomy or pf.anatomy,
                current_text=cf.text,
                prior_text=pf.text,
                current_mm=cur_mm,
                prior_mm=pri_mm,
                delta_mm=delta,
                percent_change=pct,
                match_score=round(_match_score(cf, pf), 3),
            ))

        # Unmatched current → new
        for ci, cf in enumerate(cur_findings):
            if ci in matched_cur:
                continue
            comparisons.append(FindingComparison(
                status="new",
                anatomy=cf.anatomy,
                current_text=cf.text,
                current_mm=_largest_mm(cf),
            ))

        # Unmatched prior → resolved
        for pi, pf in enumerate(pri_findings):
            if pi in matched_pri:
                continue
            comparisons.append(FindingComparison(
                status="resolved",
                anatomy=pf.anatomy,
                prior_text=pf.text,
                prior_mm=_largest_mm(pf),
            ))

        # Order: worrying first (new, increased), then stable/decreased, resolved last
        status_order = {
            "increased": 0, "new": 1, "decreased": 2, "stable": 3, "resolved": 4,
        }
        comparisons.sort(key=lambda c: status_order.get(c.status, 9))
        return ComparisonResult(comparisons=comparisons)


def compare_reports(
    current_text: str,
    prior_text: str,
    modality: Optional[str] = None,
    **comparator_kwargs,
) -> ComparisonResult:
    """
    Convenience wrapper: parse two raw report strings and compare them.

        result = compare_reports(current_txt, prior_txt, modality="CT")

    Extra keyword arguments are forwarded to ReportComparator (e.g. min_pct=25).
    """
    from .report_parser import ReportParser

    parser = ReportParser()
    current = parser.parse(current_text, modality=modality)
    prior = parser.parse(prior_text, modality=modality)
    return ReportComparator(**comparator_kwargs).compare(current, prior)
