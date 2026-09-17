#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.stlt-venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing .stlt-venv. Run ./scripts/create_env.sh first." >&2
  exit 1
fi

"$PYTHON_BIN" -m stlt_artifact.cli validate "$@"
