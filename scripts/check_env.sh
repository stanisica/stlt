#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.stlt-venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing .stlt-venv. Run ./scripts/create_env.sh first." >&2
  exit 1
fi

export MPLCONFIGDIR="$ROOT_DIR/artifact-output/.matplotlib"
export XDG_CACHE_HOME="$ROOT_DIR/artifact-output/.cache"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME"
"$PYTHON_BIN" -c 'import matplotlib, numpy, stlt_artifact; print("Environment: PASS")'
"$PYTHON_BIN" -m unittest discover -s "$ROOT_DIR/tests" -v
