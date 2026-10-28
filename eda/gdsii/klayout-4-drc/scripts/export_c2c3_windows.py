"""Export routing inspection windows from full benchmark GDS files."""
import argparse
from pathlib import Path
import klayout.db as db

from klayout_drc.benchmark.c2c3.contracts import sha256, write_json
from klayout_drc.benchmark.c2c3.evaluator import verify_dataset
from klayout_drc.benchmark.c2c3.generator import load_layout, save_layout


def export(root):
    root = Path(root)
    manifest = verify_dataset(root)
    if not manifest.complete: raise ValueError('Inspection export requires a complete qualified corpus')
    rows = []
    for case in manifest.cases:
        source = load_layout(root/case.gds)
        window = db.Region()
        for bounds in case.edit_policy['windows_um']:
            window.insert(db.Box(*(round(v/source.dbu) for v in bounds)))
        clipped = db.Layout(); clipped.dbu = source.dbu
        top = clipped.create_cell('INSPECTION_ONLY')
        for layer in case.edit_policy['context_layers']:
            index = source.find_layer(*layer)
            if index is None: continue
            region = db.Region(source.top_cell().begin_shapes_rec(index)) & window
            top.shapes(clipped.layer(*layer)).insert(region)
        relative = f'windows/{case.case_id}.gds'
        save_layout(clipped, root/relative)
        rows.append({'case_id': case.case_id, 'full_gds': case.gds, 'full_gds_sha256': case.gds_sha256,
                     'inspection_gds': relative, 'sha256': sha256(root/relative),
                     'windows_um': case.edit_policy['windows_um'], 'layers': case.edit_policy['context_layers']})
    receipt = {'case_count': len(rows), 'purpose': 'Inspection only; never substitute these clips for full scored inputs',
               'coordinate_frame': 'Original top-cell coordinates and DBU; routing layers only; flattened', 'windows': rows}
    write_json(root/'windows/manifest.json', receipt)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('dataset', type=Path)
    args = parser.parse_args()
    print(f"Exported {export(args.dataset)['case_count']} inspection windows")
