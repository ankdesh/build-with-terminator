"""One attempt per entry, with acceptance gates and durable checkpoints."""
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from pathlib import Path
import time
from .manifest import BenchmarkManifestManager as Manifests
from .scorer import BenchmarkScorer
from .types import EvaluationResult, BenchmarkVerdict as V
from .acceptance import verify_case
from ..config import DEFAULT_RUNS_DIR
from ..profile import DRCProfileManager
from ..run_manifest import RunSpec
from ..single_shot import SingleShotOrchestrator
from ..marker_comparison import compare_markers
from ..parser import DRCParser


class BenchmarkEvaluator:
    def __init__(self, base_dir, output_dir=None, profile_name='asap7_curated', profile_manager=None, workers=4):
        self.workers = workers
        if not 1 <= workers <= 4:
            raise ValueError("Workers must be between 1 and 4")
        self.base_dir = Path(base_dir).resolve()
        self.profile_name = profile_name
        self.profile_manager = profile_manager or DRCProfileManager()
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        self.output_dir = Path(output_dir) if output_dir else DEFAULT_RUNS_DIR / f'benchmark_{stamp}'
        self.runs_dir = self.output_dir/'runs'
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def evaluate_case(self, case, mode='heuristic', candidate_script=None):
        started = time.perf_counter()
        profile = self.profile_manager.get_profile(self.profile_name)
        result = EvaluationResult(case.case_id, case.rule_id, case.tier, mode, None, None,
                                  None, None, V.ORACLE_MISMATCH, None, None, 0.,
                                  initially_clean=case.expected_initial_violations == 0,
                                  duplicate_group=case.acceptance.get('duplicate_group'))
        try:
            verify_case(case, self.base_dir, profile)
            spec = RunSpec(case_name=case.case_id, input_gds=self.base_dir/case.gds_rel_path,
                           drc_script=profile.deck_path, profile_name=self.profile_name,
                           candidate_mode=mode, candidate_script=candidate_script, output_root=self.runs_dir,
                           expected_counts=case.acceptance['observed_counts'],
                           expected_markers=case.acceptance['observed_markers'],
                           preservation=case.acceptance['preservation'])
            orchestrator = SingleShotOrchestrator(spec, self.profile_manager)
            result.run_dir = str(orchestrator.paths.run_dir)
            summary = orchestrator.run()
            result.actual_mode = spec.candidate_mode if summary.verdict not in ("blocked", "oracle_mismatch") else None
            result.pipeline_verdict = summary.verdict
            result.initial_violations = summary.violations_before
            result.final_violations = summary.violations_after
            result.initial_total, result.final_total = summary.total_before, summary.total_after
            result.validation = summary.validation_result.to_dict() if summary.validation_result else None
            result.validation_level = summary.validation_level
            result.error_message = summary.error_message
            if summary.diff_report:
                result.area_added_um2 = summary.diff_report.total_added_area_um2
                result.area_removed_um2 = summary.diff_report.total_removed_area_um2
            if summary.total_after is not None:
                result.marker_comparison = compare_markers(DRCParser().parse(orchestrator.paths.before_lyrdb),
                                                           DRCParser().parse(orchestrator.paths.after_lyrdb),
                                                           profile.manufacturing_grid_um)
            result.verdict = BenchmarkScorer.classify_verdict(
                result.initial_violations, result.final_violations, summary.error_message,
                pipeline_verdict=summary.verdict, validation=summary.validation_result,
                changed=bool(summary.diff_report and summary.diff_report.modified_layers),
                marker_comparison=result.marker_comparison)
            if result.verdict in (V.CLEAN_SUCCESS, V.CLEAN_UNCHANGED):
                result.failure_stage = None
            else:
                result.failure_stage = {
                    V.ORACLE_MISMATCH: 'baseline', V.BLOCKED: 'infrastructure', V.CHECKER_ERROR: 'checker',
                    V.MODEL_ERROR: 'synthesis', V.INVALID_PATCH: 'preservation' if summary.validation_result else 'python_execution',
                    V.EXECUTION_ERROR: 'python_execution', V.REGRESSION: 'regression',
                    V.FAILED_UNCHANGED: 'geometry_reasoning', V.PARTIAL_SUCCESS: 'geometry_reasoning',
                    V.UNNECESSARY_EDIT: 'unnecessary_edit', V.AMBIGUOUS: 'uncertain'}.get(result.verdict, 'uncertain')
        except (ValueError, OSError, KeyError) as exc:
            result.error_message = str(exc)
            result.failure_stage = 'infrastructure' if result.run_dir else 'baseline'
            result.verdict = V.EXECUTION_ERROR if result.run_dir else V.ORACLE_MISMATCH
        except Exception as exc:
            result.verdict = V.EXECUTION_ERROR
            result.failure_stage = 'infrastructure'
            result.error_message = str(exc)
        result.execution_time_s = time.perf_counter()-started
        if result.run_dir:
            directory = Path(result.run_dir)
            output = directory/'benchmark_result.json'
            output.write_text(json.dumps(result.to_dict(), indent=2))
            manifest_path = directory/'run_manifest.json'
            if manifest_path.exists():
                audit = json.loads(manifest_path.read_text())
                audit.setdefault('artifact_hashes', {})[output.name] = Manifests.compute_sha256(output)
                manifest_path.write_text(json.dumps(audit, indent=2))
        return result

    def evaluate_batch(self, cases, mode='heuristic', candidate_script=None, verbose=True):
        # Exclusive campaign lock prevents concurrent duplicate requests. Do not silently
        # remove a stale lock: an interrupted request needs manual status inspection.
        batch_start = time.perf_counter()
        lock = self.output_dir/'.campaign.lock'
        with lock.open('x'):
            pass
        try:
            manifest = Manifests.load(self.base_dir/'manifest.json')
            model_config = None
            if mode == 'agent':
                config_script = Path(__file__).resolve().parents[3]/'harness/scripts/model-config.mjs'
                model_config = json.loads(subprocess.check_output(
                    ['node', str(config_script)], text=True, timeout=10))
            identity = {'schema_version': 2, 'benchmark_version': manifest.benchmark_version,
                        'manifest_sha256': Manifests.compute_sha256(self.base_dir/'manifest.json'),
                        'profile': self.profile_name, 'mode': mode, 'workers': self.workers, 'case_ids': [c.case_id for c in cases],
                        'model': model_config['model'] if model_config else None,
                        'temperature': model_config['temperature'] if model_config else None,
                        'model_config': model_config,
                        'script_sha256': Manifests.compute_sha256(candidate_script) if candidate_script else None,
                        'source_sha256': self._source_digest()}
            campaign = self.output_dir/'campaign.json'
            if campaign.exists():
                if json.loads(campaign.read_text()) != identity:
                    raise ValueError('Campaign configuration changed; use a new output directory')
            else:
                campaign.write_text(json.dumps(identity, indent=2))
                (self.output_dir/'frozen_source.json').write_text(json.dumps(self._source_bundle(), indent=2, sort_keys=True))
            frozen = json.loads((self.output_dir/'frozen_source.json').read_text())
            if hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest() != identity['source_sha256']:
                raise ValueError('Frozen source bundle does not match campaign identity')
            from concurrent.futures import ThreadPoolExecutor, as_completed
            collected = {}
            checkpoint = self.output_dir/'cases'; checkpoint.mkdir(exist_ok=True)
            pending = []
            for case in cases:
                path = checkpoint/f'{case.case_id}.json'
                claim = checkpoint/f'{case.case_id}.attempt.json'
                if path.exists():
                    collected[case.case_id] = EvaluationResult.from_dict(json.loads(path.read_text()))
                elif claim.exists():
                    raise ValueError(f'Interrupted attempt for {case.case_id}; inspect artifacts. No automatic retry.')
                else:
                    pending.append(case)

            def execute(case):
                claim = checkpoint/f'{case.case_id}.attempt.json'
                with claim.open('x') as handle:
                    json.dump({'case_id': case.case_id, 'mode': mode,
                               'started_at': datetime.now(timezone.utc).isoformat()}, handle)
                return self.evaluate_case(case, mode, candidate_script)

            def persist(case, result):
                path = checkpoint/f'{case.case_id}.json'
                temporary = path.with_suffix('.tmp')
                temporary.write_text(json.dumps(result.to_dict(), indent=2)); temporary.replace(path)
                collected[case.case_id] = result
                results = [collected[c.case_id] for c in cases if c.case_id in collected]
                self._export(BenchmarkScorer.aggregate(manifest.benchmark_version, mode, results,
                                                       sum(r.execution_time_s for r in results)))
                if verbose:
                    print(f'{case.case_id}: {result.verdict.value}', flush=True)

            # Validate infrastructure with the first requested model attempt before
            # dispatching the remaining independent requests. Never retry that attempt.
            if mode == 'agent' and pending and not collected:
                first = pending.pop(0)
                pilot = execute(first); persist(first, pilot)
                infra_failure = pilot.verdict in (V.BLOCKED, V.ORACLE_MISMATCH, V.CHECKER_ERROR) or (pilot.verdict == V.MODEL_ERROR and (not pilot.run_dir or not (Path(pilot.run_dir)/'model_response.json').exists()))
                if infra_failure:
                    for case in pending:
                        result = EvaluationResult(case.case_id, case.rule_id, case.tier, mode,
                            None, None, None, None, V.BLOCKED, None, None, 0.,
                            error_message='Campaign stopped after first-case preflight/synthesis failure; no model request was sent for this entry',
                            failure_stage='infrastructure', initially_clean=case.expected_initial_violations == 0,
                            duplicate_group=case.acceptance.get('duplicate_group'))
                        persist(case, result)
                    pending = []
            with ThreadPoolExecutor(max_workers=self.workers) as pool:
                futures = {pool.submit(execute, case): case for case in pending}
                for future in as_completed(futures):
                    persist(futures[future], future.result())
            results = [collected[c.case_id] for c in cases]
            summary = BenchmarkScorer.aggregate(manifest.benchmark_version, mode, results,
                                                 sum(r.execution_time_s for r in results))
            self._export(summary)
            (self.output_dir/'timing.json').write_text(json.dumps({'batch_wall_seconds': time.perf_counter()-batch_start, 'sum_case_seconds': summary.total_runtime_s}, indent=2))
            return summary
        finally:
            lock.unlink()

    @staticmethod
    def _source_bundle():
        root = Path(__file__).resolve().parents[3]
        bundle = {}
        for directory, patterns in [('src', ['*.py']), ('harness', ['*.ts', '*.js', '*.mjs', '*.md', '*.yaml', 'package.json']), ('knowledge', ['*.md'])]:
            for path in sorted({p for pattern in patterns for p in (root/directory).rglob(pattern)
                                if 'node_modules' not in p.parts}):
                bundle[str(path.relative_to(root))] = path.read_text()
        for name in ('pyproject.toml', 'uv.lock', 'harness/tsconfig.json'):
            bundle[name] = (root/name).read_text()
        return bundle

    @classmethod
    def _source_digest(cls):
        return hashlib.sha256(json.dumps(cls._source_bundle(), sort_keys=True).encode()).hexdigest()

    def _export(self, summary):
        BenchmarkScorer.export_json(summary, self.output_dir/'summary.json')
        BenchmarkScorer.export_csv(summary, self.output_dir/'summary.csv')
        (self.output_dir/'report.md').write_text(BenchmarkScorer.export_markdown(summary))
