#!/bin/sh
set -eu
release_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
sample_state=${SAMPLE_STATE:-"$HOME/.local/state/asd-sample"}
umask 077
mkdir -p "$sample_state"
UV_PROJECT_ENVIRONMENT="$sample_state/python" uv sync --project "$release_root" --locked --no-dev --no-install-project --no-python-downloads
printf 'Python environment ready at %s/python\n' "$sample_state"
