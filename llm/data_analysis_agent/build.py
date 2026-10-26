"""Build the Linux authoring distribution or delegate the Windows runtime build."""

import argparse
from pathlib import Path
import shutil
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STATIC_DIR = ROOT_DIR / "backend" / "static"
DIST_DIR = ROOT_DIR / "dist" / "wps-ai-builder"


def build_frontend() -> bool:
    """Compile installed frontend dependencies without fetching packages."""
    vite = FRONTEND_DIR / "node_modules" / "vite" / "bin" / "vite.js"
    node = shutil.which("node")
    if not node or not vite.is_file():
        print("Install Node.js and frontend dependencies before building.")
        return False
    result = subprocess.run([node, str(vite), "build"], cwd=FRONTEND_DIR)
    return result.returncode == 0 and (STATIC_DIR / "index.html").is_file()


def create_portable_bundle() -> bool:
    """Assemble authoring source and compiled assets; Python is a builder prerequisite."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)
    for name in ("backend", "pipeline_core", "examples", "scripts", "sample_data"):
        shutil.copytree(ROOT_DIR / name, DIST_DIR / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if (ROOT_DIR / "artifacts").exists():
        shutil.copytree(ROOT_DIR / "artifacts", DIST_DIR / "artifacts", ignore=shutil.ignore_patterns("*-qa"))
    for name in ("config.py", "config.json", "launcher.py", "pyproject.toml", "requirements-runtime.txt", "README.md", "PLATFORM.md", "offline_app.py", "runtime_launcher.py"):
        shutil.copyfile(ROOT_DIR / name, DIST_DIR / name)
    print(f"Linux builder files: {DIST_DIR}")
    print("Install pinned Python dependencies and Bubblewrap, then run python launcher.py.")
    print("Windows applications are exported from accepted projects with a cached Windows runtime.")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Build WPS-AI")
    parser.add_argument("--target", choices=["builder", "windows-runtime"], default="builder")
    parser.add_argument("--skip-frontend", action="store_true")
    args = parser.parse_args()
    if args.target == "windows-runtime":
        subprocess.run([sys.executable, str(ROOT_DIR / "scripts/build_windows_runtime.py")], check=True)
        return
    if not args.skip_frontend and not build_frontend():
        raise SystemExit(1)
    if not (STATIC_DIR / "index.html").is_file():
        raise SystemExit("Build the frontend before assembling authoring files")
    create_portable_bundle()


if __name__ == "__main__":
    main()
