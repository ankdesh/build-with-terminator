"""Command line interface for the independent five-level benchmark."""
import argparse
import json
import os
from pathlib import Path
import subprocess
from .contracts import IMAGE, sha256, write_json


def export_nets(directory):
    directory = Path(directory).resolve()
    receipt = directory/'build.json'; build = json.loads(receipt.read_text())
    if build['status'] != 'complete': raise ValueError('A complete routed build is required')
    script = Path(__file__).resolve().parents[4]/'scripts/export_c2c3_odb.tcl'
    command = ['docker', 'run', '--rm', '--network=none', '--cpus=2', '--memory=1g', '--memory-swap=1g',
               '--user', f'{os.getuid()}:{os.getgid()}', '--mount', f'type=bind,src={directory},dst=/work',
               '--mount', f'type=bind,src={script},dst=/export.tcl,readonly',
               '-e', f'C2C3_INPUT_ODB=/work/{build["final"]["odb"]}', '-e', 'C2C3_NETS_JSON=/work/nets.ndjson',
               '--entrypoint', 'bash', build['image'], '-lc',
               'source /OpenROAD-flow-scripts/env.sh; openroad -exit /export.tcl']
    with (directory/'net_export.log').open('w') as handle:
        subprocess.run(command, stdout=handle, stderr=subprocess.STDOUT, check=True, timeout=120)
    rows = [json.loads(line) for line in (directory/'nets.ndjson').read_text().splitlines()]
    catalog = {key: value for key, value in rows[0].items() if key != 'kind'}
    catalog.update(schema_version=1, nets=sorted([{key: value for key, value in row.items() if key != 'kind'}
                                               for row in rows[1:]], key=lambda row: row['name']))
    write_json(directory/'nets.json', catalog)
    build['nets_sha256'] = sha256(directory/'nets.json')
    build['artifacts'].update({name: sha256(directory/name) for name in ('nets.json', 'nets.ndjson', 'net_export.log')})
    write_json(receipt, build)
    return {'status': 'complete', 'nets_sha256': build['nets_sha256']}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare'); prep.add_argument('--root', type=Path, required=True)
    build = sub.add_parser('build'); build.add_argument('--root', type=Path, required=True)
    build.add_argument('--design', choices=('gcd', 'uart'), required=True); build.add_argument('--group', type=int, choices=(0, 1), required=True)
    build.add_argument('--factor', type=float, choices=(1., .9, .8), default=1.)
    build.add_argument('--density', type=float); build.add_argument('--attempt', type=int, default=1)
    nets = sub.add_parser('export-nets'); nets.add_argument('--build-dir', type=Path, required=True)
    qual = sub.add_parser('qualify'); qual.add_argument('--output', type=Path, required=True)
    cells = sub.add_parser('generate-cells'); cells.add_argument('--output', type=Path, required=True)
    cells.add_argument('--library', type=Path, required=True); cells.add_argument('--qualification', type=Path, required=True)
    routed = sub.add_parser('generate-routed'); routed.add_argument('--dataset', type=Path, required=True)
    routed.add_argument('--bundles', type=Path, required=True); routed.add_argument('--platform', type=Path, required=True)
    select = sub.add_parser('select-sources'); select.add_argument('--root', type=Path, required=True)
    select.add_argument('--output', type=Path, required=True)
    verify = sub.add_parser('verify'); verify.add_argument('--dataset', type=Path, required=True)
    evaluate = sub.add_parser('evaluate'); evaluate.add_argument('--dataset', type=Path, required=True)
    evaluate.add_argument('--output', type=Path, required=True); evaluate.add_argument('--mode', choices=('agent', 'heuristic', 'no_change'), required=True)
    evaluate.add_argument('--allow-incomplete', action='store_true')
    compare = sub.add_parser('compare'); compare.add_argument('--campaign', type=Path, action='append', required=True)
    compare.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            from .toolchain import prepare
            result = prepare(args.root)
        elif args.command == 'build':
            from .toolchain import build_source
            result = build_source(args.root, args.design, args.group, args.factor, args.density, args.attempt)
        elif args.command == 'export-nets': result = export_nets(args.build_dir)
        elif args.command == 'qualify':
            from .rules import qualify_rules
            result = qualify_rules(args.output)
        elif args.command == 'generate-cells':
            from .generator import generate_cells
            result = generate_cells(args.output, args.library, args.qualification).to_dict()
        elif args.command == 'generate-routed':
            from .routed_generator import generate_routed
            result = generate_routed(args.dataset, json.loads(args.bundles.read_text()), args.platform).to_dict()
        elif args.command == 'select-sources':
            from .routed_generator import select_sources
            result = {'sources': select_sources(args.root, args.output)}
        elif args.command == 'verify':
            from .evaluator import verify_dataset
            result = verify_dataset(args.dataset).to_dict()
        elif args.command == 'compare':
            from .evaluator import compare_campaigns
            result = compare_campaigns(args.campaign, args.output)
        else:
            from .evaluator import evaluate
            os.environ['KLAYOUT_DRC_MODEL_PROVIDER'] = 'bedrock'
            os.environ.setdefault('BEDROCK_MODEL', 'qwen.qwen3-coder-next')
            result = evaluate(args.dataset, args.output, args.mode, args.allow_incomplete)
        print(json.dumps(result, indent=2))
        return 1 if result.get('status') in ('failed', 'blocked', 'timeout') or result.get('passed') is False else 0
    except (ValueError, OSError, KeyError, ImportError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
