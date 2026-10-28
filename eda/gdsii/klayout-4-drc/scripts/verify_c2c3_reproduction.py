"""Compare two independently generated C2+C3 corpora without hiding differences."""
import argparse
import copy
from pathlib import Path

from klayout_drc.benchmark.c2c3.contracts import sha256, write_json
from klayout_drc.benchmark.c2c3.evaluator import verify_dataset
from klayout_drc.benchmark.c2c3.generator import canonical_digest, load_layout
from klayout_drc.marker_comparison import marker_records
from klayout_drc.parser import DRCParser


def compare(left, right):
    left, right = Path(left), Path(right)
    a, b = verify_dataset(left), verify_dataset(right)
    errors, byte_differences = [], []
    if not a.complete or not b.complete:
        errors.append('Both corpora must meet all completion gates')
    rows_a = {c.case_id: c for c in a.cases}
    rows_b = {c.case_id: c for c in b.cases}
    if rows_a.keys() != rows_b.keys(): errors.append('Case identities differ')
    parser = DRCParser()
    for name in sorted(rows_a.keys() & rows_b.keys()):
        case_a, case_b = rows_a[name], rows_b[name]
        metadata = []
        for root, case in ((left, case_a), (right, case_b)):
            record = copy.deepcopy(case.to_dict())
            # Report item order can change with the public deck's worker threads.
            # Compare canonical records below; keep every byte difference visible.
            for key in ('input_report_sha256', 'reference_report_sha256'):
                record['evidence'].pop(key)
            if record['source'].get('native_public_audit'):
                record['source']['native_public_audit'].pop('report_sha256')
            metadata.append(record)
        if metadata[0] != metadata[1]: errors.append(f'{name}: stable metadata differs')
        for relative_a, relative_b in ((case_a.gds, case_b.gds),
                                     (case_a.evidence['reference_gds'], case_b.evidence['reference_gds'])):
            path_a, path_b = left/relative_a, right/relative_b
            if canonical_digest(load_layout(path_a)) != canonical_digest(load_layout(path_b)):
                errors.append(f'{name}: geometry or hierarchy differs: {relative_a}')
            if sha256(path_a) != sha256(path_b): errors.append(f'{name}: GDS bytes differ: {relative_a}')
        reports = [(case_a.evidence[k], case_b.evidence[k]) for k in ('input_report', 'reference_report')]
        if case_a.source.get('native_public_audit'):
            reports.append((case_a.source['native_public_audit']['report'], case_b.source['native_public_audit']['report']))
        for relative_a, relative_b in reports:
            path_a, path_b = left/relative_a, right/relative_b
            if marker_records(parser.parse(path_a)) != marker_records(parser.parse(path_b)):
                errors.append(f'{name}: canonical markers differ: {relative_a}')
            if sha256(path_a) != sha256(path_b): byte_differences.append(relative_a)
    return {'passed': not errors, 'case_count': len(rows_a), 'errors': errors,
            'report_byte_differences': sorted(set(byte_differences)),
            'manifest_hashes': [sha256(root/'manifest.json') for root in (left, right)],
            'checks': ['Input and reference GDS bytes', 'Canonical geometry and hierarchy',
                       'Canonical scored and public-audit markers', 'Stable policies, metrics and source metadata']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('left', type=Path); parser.add_argument('right', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.left, args.right); write_json(args.output, result)
    print(f"Reproduction: {'PASS' if result['passed'] else 'FAIL'}; {result['case_count']} cases")
    raise SystemExit(0 if result['passed'] else 1)
