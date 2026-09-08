"""
Build and distribution packaging script for WPS-AI.

Automates:
1. Compiling the Vite/React frontend into static assets embedded in backend/static/
2. Setting up the standalone portable distribution package.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT_DIR = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT_DIR / "frontend"
STATIC_DIR = ROOT_DIR / "backend" / "static"
DIST_DIR = ROOT_DIR / "dist" / "wps-ai"


def build_frontend() -> bool:
    """Build the Vite frontend and output directly to backend/static/."""
    print(">>> Building frontend React assets with Vite...")
    if not (FRONTEND_DIR / "package.json").exists():
        print("Error: frontend directory or package.json not found.")
        return False

    # Run vite build directly using local bin
    vite_bin = FRONTEND_DIR / "node_modules" / ".bin" / "vite"
    cmd = [str(vite_bin) if vite_bin.exists() else "npx", "build"] if vite_bin.exists() else ["npx", "vite", "build"]
    if vite_bin.exists():
        cmd = [str(vite_bin), "build"]
    else:
        cmd = ["npx", "vite", "build"]

    result = subprocess.run(
        cmd,
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print("Frontend build failed:\n", result.stderr)
        return False

    if not (STATIC_DIR / "index.html").exists():
        print("Error: static/index.html was not generated.")
        return False

    print(">>> Frontend build successful! Assets placed in:", STATIC_DIR)
    return True


def create_portable_bundle() -> bool:
    """Package the self-contained portable distribution folder."""
    print(f">>> Assembling portable bundle at: {DIST_DIR}")
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Copy backend and config files
    shutil.copytree(ROOT_DIR / "backend", DIST_DIR / "backend", dirs_exist_ok=True)
    shutil.copy(ROOT_DIR / "config.py", DIST_DIR / "config.py")
    shutil.copy(ROOT_DIR / "launcher.py", DIST_DIR / "launcher.py")
    shutil.copy(ROOT_DIR / "pyproject.toml", DIST_DIR / "pyproject.toml")

    # 2. Copy sample dataset
    shutil.copytree(ROOT_DIR / "sample_data", DIST_DIR / "sample_data", dirs_exist_ok=True)

    # 3. Create run scripts for Linux/macOS and Windows
    start_sh = DIST_DIR / "start.sh"
    start_sh.write_text(
        "#!/usr/bin/env bash\n"
        "cd \"$(dirname \"$0\")\"\n"
        "python3 launcher.py \"$@\"\n"
    )
    os.chmod(start_sh, 0o755)

    start_bat = DIST_DIR / "start.bat"
    start_bat.write_text(
        "@echo off\r\n"
        "cd /d \"%~dp0\"\r\n"
        "python launcher.py %*\r\n"
    )

    print(f">>> Portable package assembled at: {DIST_DIR}")
    print(">>> To run: cd dist/wps-ai && ./start.sh (or start.bat on Windows)")
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="WPS-AI Build Tool")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip rebuilding frontend")
    args = parser.parse_args()

    if not args.skip_frontend:
        if not build_frontend():
            sys.exit(1)

    if not create_portable_bundle():
        sys.exit(1)

    print(">>> Build complete!")


if __name__ == "__main__":
    main()
