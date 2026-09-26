#!/usr/bin/env bash

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="$ROOT_DIR/.stlt-venv/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing .stlt-venv. Run ./scripts/create_env.sh first." >&2
  exit 1
fi

export PYTHONPATH="$ROOT_DIR/src"
export MPLCONFIGDIR="$ROOT_DIR/.artifact-cache/matplotlib"
export XDG_CACHE_HOME="$ROOT_DIR/.artifact-cache"
export PYTHONDONTWRITEBYTECODE=1
export PIP_CACHE_DIR="$ROOT_DIR/.artifact-cache/pip"
export PIP_DISABLE_PIP_VERSION_CHECK=1
