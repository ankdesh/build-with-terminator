"""Build the reusable Windows runtime on a Windows x64 build runner."""

import json
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("Build this runtime on Windows x64. Linux exports attach the prebuilt ZIP.")
    from pipeline_core import RUNTIME_ABI, RUNTIME_VERSION
    from pipeline_core.bundle import PACKAGES, installed_versions, inventory
    subprocess.run(["pnpm.cmd", "exec", "vite", "build", "--mode", "runtime"], cwd=ROOT / "frontend", check=True)
    destination = ROOT / "dist" / "windows-runtime"
    if destination.exists():
        shutil.rmtree(destination)
    packages = PACKAGES
    command = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onedir", "--name", "WPSAnalysis",
        "--distpath", str(destination), "--workpath", str(ROOT / "dist" / "pyinstaller-work"),
        "--specpath", str(ROOT / "dist"), "--collect-submodules", "uvicorn",
        "--hidden-import", "pipeline_core.worker", "--hidden-import", "pipeline_core.statistics",
        "--hidden-import", "offline_app", "--exclude-module", "openai", "--exclude-module", "backend",
        "--exclude-module", "matplotlib", "--exclude-module", "sklearn"]
    for name in packages:
        command += ["--copy-metadata", name]
    for name in ("pandas", "numpy", "scipy", "statsmodels"):
        command += ["--collect-all", name]
    subprocess.run(command + [str(ROOT / "runtime_launcher.py")], cwd=ROOT, check=True)
    package = destination / "WPSAnalysis"
    shutil.copytree(ROOT / "runtime_static", package / "static")
    (package / "static" / "runtime.html").rename(package / "static" / "index.html")
    metadata = {"runtime_abi": RUNTIME_ABI, "runtime_version": RUNTIME_VERSION, "platform": "windows-x64",
        "entrypoint": "WPSAnalysis.exe", "versions": installed_versions(), "files": inventory(package)}
    (package / "runtime.json").write_text(json.dumps(metadata, indent=2))
    archive = ROOT / "dist" / "windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as stream:
        for path in package.rglob("*"):
            if path.is_file():
                stream.write(path, path.relative_to(package).as_posix())
    print(f"Windows runtime ready: {archive}")


if __name__ == "__main__":
    main()
