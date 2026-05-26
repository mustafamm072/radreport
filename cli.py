"""
Command-line interface for radreport-parser.

Usage:
    radreport report.txt
    radreport report.txt --fhir --patient-id pt-001 --modality CT
    radreport reports/*.txt --critical -o batch.json
"""

import argparse
import json
import sys
from pathlib import Path

from . import ReportParser, CriticalFindingsDetector, FHIRExporter

_parser = ReportParser()
_detector = CriticalFindingsDetector()
_exporter = FHIRExporter()


def _process(path: Path, modality, run_critical, as_fhir, patient_id):
    text = path.read_text(encoding="utf-8")
    report = _parser.parse(text, modality=modality)

    if run_critical:
        report = _detector.detect(report)

    if as_fhir:
        return _exporter.export(report, patient_id=patient_id)

    d = report.to_dict()
    d["source_file"] = path.name
    return d


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="radreport",
        description="Parse radiology free-text reports into structured JSON or FHIR.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
examples:
  radreport report.txt
  radreport report.txt --fhir --patient-id pt-001 --modality CT
  radreport reports/*.txt --critical -o batch.json
""",
    )
    ap.add_argument("files", nargs="+", metavar="FILE",
                    help="Report .txt file(s) to parse")
    ap.add_argument("--modality", "-m", metavar="MOD",
                    help="Imaging modality: CT, MRI, XR, US, NM, PET …")
    ap.add_argument("--critical", "-c", action="store_true",
                    help="Run critical findings detection")
    ap.add_argument("--fhir", "-f", action="store_true",
                    help="Export as FHIR R4 DiagnosticReport (implies --critical)")
    ap.add_argument("--patient-id", metavar="ID",
                    help="FHIR Patient resource ID (used with --fhir)")
    ap.add_argument("--output", "-o", metavar="FILE",
                    help="Write JSON output to FILE instead of stdout")

    args = ap.parse_args(argv)
    run_critical = args.critical or args.fhir

    results = []
    errors = []
    for f in args.files:
        p = Path(f)
        if not p.is_file():
            errors.append(f"not found: {f}")
            continue
        try:
            results.append(_process(p, args.modality, run_critical, args.fhir, args.patient_id))
        except Exception as e:
            errors.append(f"{p.name}: {e}")

    for err in errors:
        print(f"[error] {err}", file=sys.stderr)

    if not results:
        sys.exit(1)

    output = results[0] if len(results) == 1 else results
    json_str = json.dumps(output, indent=2)

    if args.output:
        Path(args.output).write_text(json_str, encoding="utf-8")
        print(f"Written to {args.output}", file=sys.stderr)
    else:
        print(json_str)


if __name__ == "__main__":
    main()
