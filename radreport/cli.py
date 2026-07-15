"""
Command-line interface for radreport.

Usage:
    radreport report.txt
    radreport report.txt --fhir --patient-id pt-001 --modality CT
    radreport reports/*.txt --critical --recommend --format csv -o batch.csv
    radreport report.txt --deidentify
"""

import argparse
import csv
import io
import json
import sys
from pathlib import Path

from . import (
    ReportParser, CriticalFindingsDetector, FHIRExporter,
    RecommendationExtractor, Deidentifier, ReportComparator,
)

_parser = ReportParser()
_detector = CriticalFindingsDetector()
_extractor = RecommendationExtractor()
_exporter = FHIRExporter()
_deidentifier = Deidentifier()
_comparator = ReportComparator()


def _process(path: Path, modality, run_critical, run_recommend, as_fhir, patient_id,
             run_deidentify=False):
    """Return (ParsedReport, output_dict). output_dict is FHIR when as_fhir=True."""
    text = path.read_text(encoding="utf-8")

    if run_deidentify:
        result = _deidentifier.deidentify(text)
        if result.redaction_count:
            print(f"[deid] {path.name}: redacted {result.redaction_count} span(s) "
                  f"({result.category_counts()})", file=sys.stderr)
        text = result.text

    report = _parser.parse(text, modality=modality)

    if run_critical:
        report = _detector.detect(report)
    if run_recommend:
        report = _extractor.extract(report)

    if as_fhir:
        return report, _exporter.export(report, patient_id=patient_id)

    d = report.to_dict()
    d["source_file"] = path.name
    return report, d


def _to_csv(rows: list[dict]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def _read_report_text(path: Path, run_deidentify: bool) -> str:
    text = path.read_text(encoding="utf-8")
    if run_deidentify:
        result = _deidentifier.deidentify(text)
        if result.redaction_count:
            print(f"[deid] {path.name}: redacted {result.redaction_count} span(s) "
                  f"({result.category_counts()})", file=sys.stderr)
        text = result.text
    return text


def _run_compare(ap, args) -> None:
    """Interval-change mode: compare a single current report against a prior study."""
    if len(args.files) != 1:
        ap.error("--compare requires exactly one input FILE (the current study)")

    current_path = Path(args.files[0])
    prior_path = Path(args.compare)
    for p in (current_path, prior_path):
        if not p.is_file():
            print(f"[error] not found: {p}", file=sys.stderr)
            sys.exit(1)

    current = _parser.parse(
        _read_report_text(current_path, args.deidentify), modality=args.modality)
    prior = _parser.parse(
        _read_report_text(prior_path, args.deidentify), modality=args.modality)

    result = _comparator.compare(current, prior)
    out = result.to_dict()
    out["current_file"] = current_path.name
    out["prior_file"] = prior_path.name
    output_str = json.dumps(out, indent=2)

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output_str)


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="radreport",
        description="Parse radiology free-text reports into structured JSON, FHIR, or CSV.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  radreport report.txt
  radreport report.txt --fhir --patient-id pt-001 --modality CT
  radreport reports/*.txt --critical --recommend --format csv -o batch.csv
  radreport report.txt --deidentify --critical
  radreport current.txt --compare prior.txt --modality CT
""",
    )
    ap.add_argument("files", nargs="+", metavar="FILE",
                    help="Report .txt file(s) to parse")
    ap.add_argument("--modality", "-m", metavar="MOD",
                    help="Imaging modality: CT, MRI, XR, US, NM, PET …")
    ap.add_argument("--critical", "-c", action="store_true",
                    help="Run critical findings detection")
    ap.add_argument("--recommend", "-r", action="store_true",
                    help="Extract follow-up imaging recommendations")
    ap.add_argument("--deidentify", "-d", action="store_true",
                    help="Redact PHI (dates, MRN, names, phone, …) before parsing")
    ap.add_argument("--compare", metavar="PRIOR",
                    help="Compare the input report against a PRIOR study .txt and "
                         "report interval change (new/increased/decreased/stable/"
                         "resolved). Requires a single input FILE; outputs JSON.")
    ap.add_argument("--fhir", "-f", action="store_true",
                    help="Export as FHIR R4 DiagnosticReport (implies --critical; not compatible with --format csv)")
    ap.add_argument("--patient-id", metavar="ID",
                    help="FHIR Patient resource ID (used with --fhir)")
    ap.add_argument("--format", "--fmt", dest="fmt", metavar="FMT",
                    choices=["json", "csv"], default="json",
                    help="Output format: json (default) or csv (flat one-row-per-report)")
    ap.add_argument("--output", "-o", metavar="FILE",
                    help="Write output to FILE instead of stdout")

    args = ap.parse_args(argv)

    if args.fmt == "csv" and args.fhir:
        ap.error("--format csv is not compatible with --fhir")

    if args.compare:
        return _run_compare(ap, args)

    run_critical = args.critical or args.fhir
    run_recommend = args.recommend

    reports = []   # (ParsedReport, path) for CSV mode
    json_rows = [] # dicts for JSON mode
    errors = []

    for f in args.files:
        p = Path(f)
        if not p.is_file():
            errors.append(f"not found: {f}")
            continue
        try:
            report_obj, out = _process(p, args.modality, run_critical, run_recommend,
                                        args.fhir, args.patient_id, args.deidentify)
            if args.fmt == "csv":
                flat = report_obj.to_flat_dict()
                reports.append({"source_file": p.name, **flat})
            else:
                json_rows.append(out)
        except Exception as e:
            errors.append(f"{p.name}: {e}")

    for err in errors:
        print(f"[error] {err}", file=sys.stderr)

    if not reports and not json_rows:
        sys.exit(1)

    if args.fmt == "csv":
        output_str = _to_csv(reports)
    else:
        output = json_rows[0] if len(json_rows) == 1 else json_rows
        output_str = json.dumps(output, indent=2)

    if args.output:
        Path(args.output).write_text(output_str, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(output_str)


if __name__ == "__main__":
    main()
