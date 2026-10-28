"""Dataset checks use retained qualification and oracle bytes."""
import json
from pathlib import Path
from .archive import dataset_catalog, sha


def verify_data(data_root, suite='all'):
    data_root = Path(data_root)
    result = {}
    if suite in ('all', 'ab'):
        paths = list((data_root/'layouts').glob('*/*.gds'))
        if not paths: raise ValueError('Missing A/B fixtures')
        import klayout.db as db
        for p in paths:
            layout = db.Layout(); layout.read(str(p))
            if layout.top_cell() is None: raise ValueError(f'Empty A/B fixture: {p}')
        result['ab'] = {'fixtures': len(paths), 'sha256': {str(p.relative_to(data_root)): sha(p) for p in paths}}
    if suite in ('all', 'c1'):
        from ..cli import execute_benchmark_verify
        c1 = execute_benchmark_verify(data_root/'benchmark_v1')
        if not c1['all_valid'] or c1['total_cases'] != 100: raise ValueError(f'C1 integrity failed: {c1}')
        result['c1'] = c1
    if suite in ('all', 'c2c3'):
        from ..benchmark.c2c3.evaluator import verify_dataset
        m = verify_dataset(data_root/'benchmark_c2c3')
        if not m.complete or len(m.cases) != 50: raise ValueError('C2+C3 requires all 50 accepted cases')
        result['c2c3'] = {'complete': m.complete, 'cases': len(m.cases)}
    return {'status': 'verified', 'datasets': result}
