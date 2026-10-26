"""Optional live-model acceptance check using a tiny synthetic CSV."""

import argparse
import asyncio
import json
import httpx
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a live builder check; consumes configured model calls")
    parser.add_argument("--url", default="http://127.0.0.1:8080")
    parser.add_argument("--live-model", action="store_true", required=True)
    parser.add_argument("--in-process", action="store_true", help="Exercise the real ASGI API without a separate test server")
    parser.add_argument("--project-id", help="Resume a previously generated synthetic reference project")
    args = parser.parse_args()
    asyncio.run(check(args))


async def check(args: argparse.Namespace) -> None:
    transport = None
    if args.in_process:
        from backend.app import app
        transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(base_url=args.url, transport=transport, timeout=300) as client:
        if args.project_id:
            project_id = args.project_id
        else:
            project = await client.post('/api/projects', json={'title': 'Live generation validation'})
            project.raise_for_status()
            project_id = project.json()['id']
        base = '/api/projects/' + project_id
        if not args.project_id:
            upload = await client.post(base + '/dataset', files={'csv_file': ('reference.csv', b'category,amount\nA,10\nA,20\nB,30\n')},
                data={'description': 'Synthetic reference data. category is a label; amount is a numeric measurement.'})
            upload.raise_for_status()

        async def operation(path: str, body: dict) -> None:
            response = await client.post(path, json=body)
            response.raise_for_status()
            errors = []
            for frame in response.text.replace('\r\n', '\n').split('\n\n'):
                data = '\n'.join(line[5:].strip() for line in frame.split('\n') if line.startswith('data:'))
                if not data:
                    continue
                event = json.loads(data)
                if event['event'] == 'error': errors.append(event['message'])
            if errors:
                raise RuntimeError(errors)

        if not args.project_id:
            await operation(base + '/chat', {'query': 'Create a dashboard with the sum of amount, a category totals bar chart and full table, and computed text showing current row count. Add a category select filter with All as the null default. Add a multiplier numeric control with default 1, minimum 0 and maximum 10, and an adjusted-total metric. Cleanup must pass data unchanged; do not drop or impute any rows.'})
        view = (await client.get(base)).json()
        run = view['display_run']
        assert run and run['status'] == 'succeeded', view
        metrics = [out['value'] for out in run['result'].get('widgets', run['result']['outputs']).values() if out['kind'] == 'metric']
        assert metrics and all(value == 60 for value in metrics), metrics
        draft = view['draft']
        multiplier = next(p['id'] for p in draft['parameters'] if not p['filter_column'] and 'multiplier' in p['label'].lower())
        await operation(base + '/revisions/' + draft['revision_id'] + '/run', {'parameters': {multiplier: 2}})
        updated = (await client.get(base)).json()['display_run']
        assert 120 in [out['value'] for out in updated['result'].get('widgets', updated['result']['outputs']).values() if out['kind'] == 'metric']
        category = next(p['id'] for p in draft['parameters'] if p['filter_column'] == 'category')
        await operation(base + '/revisions/' + draft['revision_id'] + '/run', {'parameters': {category: 'A'}})
        filtered = (await client.get(base)).json()['display_run']['result']
        assert 30 in [out['value'] for out in filtered.get('widgets', filtered['outputs']).values() if out['kind'] == 'metric']
        await operation(base + '/chat', {'query': 'Change /dashboard/title to Generated Validation Dashboard. Use a targeted patch. Preserve all steps, Python source, controls, widgets and bindings.'})
        refined = (await client.get(base)).json()
        assert refined['draft']['dashboard']['title'] == 'Generated Validation Dashboard'
        assert refined['draft']['steps'] == draft['steps']
        assert refined['draft']['parameters'] == draft['parameters']
        accepted = await client.post(base + '/accept', json={'run_id': refined['display_run']['run_id'], 'cleanup_confirmed': True})
        accepted.raise_for_status()
        print(f"Live model creation, known sums, parameter calculations, targeted refinement and acceptance passed. Project: {project_id}")


if __name__ == '__main__':
    main()
