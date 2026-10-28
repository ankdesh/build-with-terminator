"""Single-shot DRC layout repair orchestrator.

Chains the single-attempt Fix -> Apply Patch -> Report pipeline across:
preflight DRC, candidate acquisition, out-of-process execution, layout validation,
DRC re-check, and truthful audit reporting.
"""

import json
import os
from dataclasses import replace
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

from .config import DRCJobConfig, DRCConfigurationError
from .api_reference import APIReferenceError, verify_api_reference
from .parser import DRCParser
from .profile import DRCProfileManager, DRCProfile
from .runner import DRCRunner
from .repair_executor import RepairExecutor, ExecutionResult, sandbox_availability
from .marker_comparison import marker_records, compare_markers
from .validator import LayoutValidator, ValidationResult
from .layout_diff import LayoutDiffCalculator, LayoutDiffReport
from .run_manifest import RunManifestManager, RunSpec, RunPaths
from .run_reporter import (
    RunReporter,
    EvaluationSummary,
)


class SingleShotOrchestrator:
    """Orchestrates end-to-end single-shot layout evaluation and repair verification."""

    def __init__(self, spec: RunSpec, profile_manager: DRCProfileManager | None = None) -> None:
        """Initialize orchestrator with validated run specification and profile manager.

        Args:
            spec: Run specification containing input paths, mode, and target profile.
            profile_manager: Optional profile manager; defaults to a new DRCProfileManager.
        """
        self.spec = spec
        self.profile_manager = profile_manager or DRCProfileManager()
        self.profile: DRCProfile = self.profile_manager.get_profile(spec.profile_name)

        if spec.drc_script.resolve() != self.profile.deck_path.resolve():
            raise DRCConfigurationError("Run deck conflicts with selected profile")
        self.manifest_manager = RunManifestManager(spec)
        self.paths: RunPaths = self.manifest_manager.setup_run()
        snapshot = self.paths.run_dir / ("deck" + self.spec.drc_script.suffix)
        self.profile = replace(self.profile, deck_path=snapshot)
        self.reporter = RunReporter(
            run_id=self.manifest_manager.run_id,
            case_name=self.spec.case_name,
            profile_name=self.spec.profile_name,
            candidate_mode=self.spec.candidate_mode,
            output_dir=self.paths.run_dir,
        )

    def _run_drc(self, layout_path: Path, output_lyrdb: Path) -> tuple[dict[str, int], int]:
        """Execute DRC on layout using profile parameters and parse violation counts."""
        config = DRCJobConfig(
            input_gds=layout_path,
            drc_script=self.profile.deck_path,
            output_lyrdb=output_lyrdb,
            param_in_gds=self.profile.param_in_gds,
            param_report=self.profile.param_report,
            extra_params=self.profile.extra_params,
        )
        runner = DRCRunner(config)
        runner.run()

        parser = DRCParser()
        data = parser.parse(output_lyrdb)
        return data.rule_summary, data.total_violations

    def _acquire_candidate_script(self) -> str | None:
        """Acquire or synthesize candidate repair script based on candidate_mode.

        Returns:
            str | None: Error message if acquisition fails, None on success.
        """
        mode = self.spec.candidate_mode

        if mode == "script_file":
            if not self.spec.candidate_script or not self.spec.candidate_script.exists():
                return f"Candidate script file does not exist: {self.spec.candidate_script}"
            shutil.copy2(self.spec.candidate_script, self.paths.candidate_script)
            return None

        if mode == "heuristic":
            # Generate deterministic heuristic repair script targeting profile layers
            m1_layer, m1_dt = self.profile.layers.get("M1", (18, 0))
            m2_layer, m2_dt = self.profile.layers.get("M2", (20, 0))
            v1_layer, v1_dt = self.profile.layers.get("V1", (19, 0))

            is_legacy = self.spec.profile_name == "legacy_mini"

            v1_width_snippet = "" if is_legacy else """
        # Fix V1 width: expand narrow via cuts (< 18nm)
        min_v1_dbu = int(round(0.018 / dbu))
        v1_err = v1_reg.width_check(min_v1_dbu)
        if not v1_err.is_empty():
            v1_reg = v1_reg | v1_err.polygons(0).sized(int(round(0.005 / dbu)))
            top.shapes(v1_idx).clear()
            top.shapes(v1_idx).insert(v1_reg)
"""

            m1_area_snippet = "" if is_legacy else """
        # Fix area: expand small islands (< 504 nm2)
        min_area_dbu2 = int(round(0.000504 / (dbu * dbu)))
        small_polys = m1_reg.with_area(0, min_area_dbu2)
        if not small_polys.is_empty():
            m1_reg = m1_reg | small_polys.sized(int(round(0.006 / dbu)))
"""

            heuristic_code = f"""#!/usr/bin/env python3
\"\"\"Deterministic Heuristic DRC Repair Script for ASAP7.\"\"\"
import sys
from pathlib import Path
import klayout.db as db

def fix_layout(input_gds: str, output_gds: str) -> None:
    layout = db.Layout()
    layout.read(str(input_gds))
    top = layout.top_cell()
    if top is None:
        raise RuntimeError("No top cell found in layout.")

    dbu = layout.dbu
    # Layer indices
    m1_idx = layout.find_layer({m1_layer}, {m1_dt})
    m2_idx = layout.find_layer({m2_layer}, {m2_dt})
    v1_idx = layout.find_layer({v1_layer}, {v1_dt})

    m1_reg = db.Region(top.shapes(m1_idx)) if m1_idx is not None else db.Region()
    m2_reg = db.Region(top.shapes(m2_idx)) if m2_idx is not None else db.Region()
    v1_reg = db.Region(top.shapes(v1_idx)) if v1_idx is not None else db.Region()

    # 1. Enclosure pad V1 by 9nm on M1 (if legacy mini)
    if not v1_reg.is_empty():
        enc_pad_dbu = int(round(0.009 / dbu))
        m1_reg = m1_reg | v1_reg.sized(enc_pad_dbu)
{v1_width_snippet}

    # 2. Fix M1 width and area
    if not m1_reg.is_empty():
        merge_dbu = int(round(0.009 / dbu))
        m1_reg = m1_reg.sized(merge_dbu).sized(-merge_dbu)

        # Fix width: expand narrow regions (< 18nm)
        min_width_dbu = int(round(0.018 / dbu))
        width_boost_dbu = int(round(0.005 / dbu))
        error_edges = m1_reg.width_check(min_width_dbu)
        m1_reg = m1_reg | error_edges.polygons(0).sized(width_boost_dbu)
{m1_area_snippet}

        if m1_idx is None:
            m1_idx = layout.layer({m1_layer}, {m1_dt})
        top.shapes(m1_idx).clear()
        top.shapes(m1_idx).insert(m1_reg)

    # 3. Fix M2 width
    if not m2_reg.is_empty():
        min_width_dbu = int(round(0.018 / dbu))
        width_boost_dbu = int(round(0.005 / dbu))
        error_edges_m2 = m2_reg.width_check(min_width_dbu)
        if not error_edges_m2.is_empty():
            m2_reg = m2_reg | error_edges_m2.polygons(0).sized(width_boost_dbu)
            if m2_idx is None:
                m2_idx = layout.layer({m2_layer}, {m2_dt})
            top.shapes(m2_idx).clear()
            top.shapes(m2_idx).insert(m2_reg)

    Path(output_gds).parent.mkdir(parents=True, exist_ok=True)
    layout.write(str(output_gds))

if __name__ == "__main__":
    in_path = sys.argv[1] if len(sys.argv) > 1 else "input.gds"
    out_path = sys.argv[2] if len(sys.argv) > 2 else "patched.gds"
    fix_layout(in_path, out_path)
"""
            self.paths.candidate_script.write_text(heuristic_code, encoding="utf-8")
            return None

        if mode == "agent":
            # Invoke DeepSeek Harness flow runner
            harness_runner = Path(__file__).resolve().parent.parent.parent / "harness" / "scripts" / "run-flow.mjs"
            if not harness_runner.exists():
                return f"DeepSeek Harness runner not found: {harness_runner}"

            cmd = [
                "node",
                str(harness_runner),
                "--gds", str(self.paths.input_gds),
                "--deck", str(self.profile.deck_path),
                "--report-db", str(self.paths.before_lyrdb),
                "--output-script", str(self.paths.candidate_script),
                "--profile", self.spec.profile_name,
                "--reuse-report", "--artifact-dir", str(self.paths.run_dir),
                "--text-report", str(self.paths.run_dir / "violations.txt"),
            ]
            if self.spec.edit_policy is not None:
                policy_path = self.paths.run_dir / 'edit_policy.json'
                policy_path.write_text(json.dumps(self.spec.edit_policy, indent=2))
                cmd += ['--edit-policy', str(policy_path)]
            try:
                res = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                    env={**os.environ, "KLAYOUT_DRC_PYTHON": sys.executable},
                )
                (self.paths.run_dir / "generation_stdout.log").write_text(res.stdout)
                (self.paths.run_dir / "generation_stderr.log").write_text(res.stderr)
                if res.returncode != 0:
                    return f"Agent synthesis failed with code {res.returncode}: {res.stderr.strip() or res.stdout.strip()}"
                if not self.paths.candidate_script.exists():
                    return "Agent flow finished with code 0 but candidate script was not written."
                return None
            except Exception as exc:
                return f"Agent invocation failed: {exc}"

        return f"Unknown candidate mode: {mode}"

    def run(self) -> EvaluationSummary:
        try:
            return self._run()
        except Exception as exc:
            execution = ExecutionResult("nonzero_exit", None, 0., "", str(exc), None, str(exc))
            summary = self.reporter.evaluate(execution, getattr(self, "_before", None),
                                             sum(self._before.values()) if getattr(self, "_before", None) is not None else None)
            self._write_artifacts(summary)
            return summary

    def _run(self) -> EvaluationSummary:
        """Execute the full single-shot evaluation pipeline."""
        # A pinned deck selects the unique layout top. Reject unsupported ambiguity.
        import klayout.db as db
        layout = db.Layout(); layout.read(str(self.paths.input_gds))
        tops = list(layout.top_cells())
        if len(tops) != 1 or (self.spec.top_cell and tops[0].name != self.spec.top_cell):
            raise DRCConfigurationError("Require one top cell matching the requested top cell")
        self.manifest_manager.update_manifest({"resolved_top_cell": tops[0].name})
        # 1. Preflight baseline DRC
        try:
            viols_before, total_before = self._run_drc(self.paths.input_gds, self.paths.before_lyrdb)
        except Exception as exc:
            # Baseline DRC failure
            dummy_exec = ExecutionResult(
                status="drc_error",
                exit_code=1,
                duration_seconds=0.0,
                stdout="",
                stderr=str(exc),
                output_gds=None,
                error_message=f"Preflight DRC failed: {exc}",
            )
            summary = self.reporter.evaluate(
                execution=dummy_exec,
                violations_before=None,
                total_before=None,
                drc_error=str(exc),
            )
            self._write_artifacts(summary)
            return summary

        self._before = viols_before
        if self.spec.edit_policy is not None:
            from .edit_policy import policy_context, ContextIncomplete
            try:
                context = policy_context(self.paths.input_gds, self.spec.edit_policy)
                (self.paths.run_dir/'policy_context.json').write_text(json.dumps(context, indent=2))
            except ContextIncomplete as exc:
                execution = ExecutionResult('blocked', None, 0., '', str(exc), None, str(exc))
                summary = self.reporter.evaluate(execution, viols_before, total_before)
                self._write_artifacts(summary)
                return summary
        if self.spec.expected_counts is not None and viols_before != self.spec.expected_counts:
            execution = ExecutionResult("oracle_mismatch", None, 0., "", "Baseline counts differ from accepted oracle", None,
                                        "Baseline counts differ from accepted oracle")
            summary = self.reporter.evaluate(execution, viols_before, total_before)
            self._write_artifacts(summary)
            return summary
        if self.spec.expected_markers is not None:
            observed = json.loads(json.dumps(marker_records(DRCParser().parse(self.paths.before_lyrdb))))
            if observed != self.spec.expected_markers:
                execution = ExecutionResult("oracle_mismatch", None, 0., "", "Baseline markers differ from accepted oracle", None,
                                            "Baseline markers differ from accepted oracle")
                summary = self.reporter.evaluate(execution, viols_before, total_before)
                self._write_artifacts(summary)
                return summary
        blocked = sandbox_availability()
        if not blocked and self.spec.candidate_mode == 'agent':
            try:
                reference = verify_api_reference()
                (self.paths.run_dir/'api_reference_check.json').write_text(json.dumps(reference, indent=2))
            except APIReferenceError as exc:
                blocked = str(exc)
        if blocked:
            execution = ExecutionResult("blocked", None, 0., "", blocked, None, blocked)
            summary = self.reporter.evaluate(execution, viols_before, total_before)
            self._write_artifacts(summary)
            return summary
        # 2. Acquire candidate repair script
        gen_error = self._acquire_candidate_script()
        if gen_error:
            error_path = self.paths.run_dir/'generation_error.json'
            reference_failed = error_path.exists() and json.loads(error_path.read_text()).get('stage') == 'api_reference'
            dummy_exec = ExecutionResult(
                status="blocked" if reference_failed else "model_error",
                exit_code=1,
                duration_seconds=0.0,
                stdout="",
                stderr=gen_error,
                output_gds=None,
                error_message=gen_error,
            )
            summary = self.reporter.evaluate(
                execution=dummy_exec,
                violations_before=viols_before,
                total_before=total_before,
                generation_error=gen_error,
            )
            self._write_artifacts(summary)
            return summary

        # Record candidate script hash in manifest
        script_hash = RunManifestManager.compute_sha256(self.paths.candidate_script)
        self.manifest_manager.update_manifest({"candidate_script_sha256": script_hash})

        # 3. Execute patch out-of-process
        executor = RepairExecutor(
            candidate_script=self.paths.candidate_script,
            input_gds=self.paths.input_gds,
            output_gds=self.paths.patched_gds,
        )
        exec_res = executor.execute()
        self.paths.candidate_stdout.write_text(exec_res.stdout, encoding="utf-8")
        self.paths.candidate_stderr.write_text(exec_res.stderr, encoding="utf-8")

        if exec_res.status != "success":
            summary = self.reporter.evaluate(
                execution=exec_res,
                violations_before=viols_before,
                total_before=total_before,
            )
            self._write_artifacts(summary)
            return summary

        manifest = json.loads(self.paths.run_manifest_json.read_text())
        immutable = {self.paths.input_gds: manifest["hashes"]["input_gds_sha256"],
                     self.profile.deck_path: manifest["hashes"]["drc_script_sha256"],
                     self.spec.input_gds: manifest["hashes"]["input_gds_sha256"],
                     self.spec.drc_script: manifest["hashes"]["drc_script_sha256"]}
        if any(RunManifestManager.compute_sha256(path) != digest for path, digest in immutable.items()):
            raise RuntimeError("Immutable input or deck hash changed")
        # 4. Validate layout integrity
        protected_set = set(self.profile.protected_cells) if self.profile.protected_cells else None
        if self.spec.edit_policy is not None:
            protected_set = {c.name for c in layout.each_cell()} - set(self.spec.edit_policy['editable_cells'])
        validator = LayoutValidator(
            self.paths.patched_gds,
            reference_gds=self.paths.input_gds,
            protected_cells=protected_set,
            preservation=self.spec.preservation,
            top_cell=self.spec.top_cell,
        )
        val_res = validator.validate()
        if self.spec.edit_policy is not None and val_res.is_valid:
            from .edit_policy import validate_edit_policy
            candidate_layout = db.Layout(); candidate_layout.read(str(self.paths.patched_gds))
            errors = validate_edit_policy(layout, candidate_layout, self.spec.edit_policy)
            if errors:
                val_res = replace(val_res, is_valid=False, violations=val_res.violations + errors)

        if not val_res.is_valid:
            summary = self.reporter.evaluate(
                execution=exec_res,
                violations_before=viols_before,
                total_before=total_before,
                validation=val_res,
            )
            self._write_artifacts(summary)
            return summary

        # 5. Compute geometric diff
        diff_calc = LayoutDiffCalculator(self.paths.input_gds, self.paths.patched_gds)
        diff_rep = diff_calc.compute_diff()
        self.paths.layout_diff_json.write_text(
            json.dumps(diff_rep.to_dict(), indent=2), encoding="utf-8"
        )

        # 5b. Verify edit scope against profile editable_layers
        if self.profile.editable_layers:
            allowed_tuples = {
                self.profile.layers[l]
                for l in self.profile.editable_layers
                if l in self.profile.layers
            }
            for mod_ly in diff_rep.modified_layers:
                if tuple(mod_ly) not in allowed_tuples:
                    scope_err = (
                        f"Edit scope violation: layer {mod_ly[0]}/{mod_ly[1]} was modified "
                        f"but is not in allowed editable layers {self.profile.editable_layers}."
                    )
                    val_res = ValidationResult(
                        is_valid=False,
                        top_cell_name=val_res.top_cell_name,
                        dbu_um=val_res.dbu_um,
                        total_shapes=val_res.total_shapes,
                        bbox_um=val_res.bbox_um,
                        violations=list(val_res.violations) + [scope_err],
                    )
                    summary = self.reporter.evaluate(
                        execution=exec_res,
                        violations_before=viols_before,
                        total_before=total_before,
                        validation=val_res,
                        diff_report=diff_rep,
                    )
                    self._write_artifacts(summary)
                    return summary

        # 6. Re-check DRC on patched GDS with identical deck & profile
        try:
            viols_after, total_after = self._run_drc(self.paths.patched_gds, self.paths.after_lyrdb)
            drc_err = None
        except Exception as exc:
            viols_after = None
            total_after = None
            drc_err = f"Re-check DRC failed: {exc}"

        # 7. Generate consolidated report and write artifacts
        summary = self.reporter.evaluate(
            execution=exec_res,
            violations_before=viols_before,
            total_before=total_before,
            violations_after=viols_after,
            total_after=total_after,
            validation=val_res,
            diff_report=diff_rep,
            drc_error=drc_err,
            marker_comparison=compare_markers(DRCParser().parse(self.paths.before_lyrdb), DRCParser().parse(self.paths.after_lyrdb), self.profile.manufacturing_grid_um) if drc_err is None else None,
        )
        self._write_artifacts(summary)
        return summary

    def _write_artifacts(self, summary: EvaluationSummary) -> None:
        """Write results.json and report.md, and update run manifest."""
        self.reporter.write_results_json(summary, self.paths.results_json)
        self.reporter.write_report_md(summary, self.paths.report_md)
        artifacts = {p.name: RunManifestManager.compute_sha256(p)
                     for p in self.paths.run_dir.iterdir() if p.is_file() and p != self.paths.run_manifest_json}
        self.manifest_manager.update_manifest({
            "artifact_hashes": artifacts,
            "verdict": summary.verdict,
            "validation_level": summary.validation_level,
            "total_before": summary.total_before,
            "total_after": summary.total_after,
        })
