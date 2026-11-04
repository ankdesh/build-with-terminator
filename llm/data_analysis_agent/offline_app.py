"""Verified offline package adapter for the shared dashboard runtime."""

import os
from pathlib import Path

from fastapi import FastAPI

from pipeline_core.bundle import load_bundle
from pipeline_core.runtime import Runner, RuntimeApplication
from pipeline_core.runtime_http import create_runtime_app


class OfflineApplication(RuntimeApplication):
    def __init__(self, package: Path, state_dir: Path, runner: Runner | None = None) -> None:
        revision, self.manifest = load_bundle(package)
        self.package = package
        super().__init__(state_dir, revision, runner)
        source = package / "input" / "data.csv"
        if not self.state.get("input") and source.is_file():
            destination = self.copy_input(source)
            self.state.update(input=str(destination), dataset_name=self.manifest["dataset_name"])
            self.save()


def create_app(package: Path, state_dir: Path | None = None, runner: Runner | None = None) -> FastAPI:
    revision, _ = load_bundle(package)
    root = state_dir or Path(os.environ.get("LOCALAPPDATA", str(Path.home() / ".local/share"))) / "WPSAnalysis" / revision.revision_id
    return create_runtime_app(OfflineApplication(package, root, runner), package / "static")
