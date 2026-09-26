#!/usr/bin/env bash
set -euo pipefail
export PIP_DISABLE_PIP_VERSION_CHECK=1
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.stlt-venv"
PYTHON_COMMAND="${PYTHON:-python3.12}"
"$PYTHON_COMMAND" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Python 3.12 is required"'
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_COMMAND" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Existing environment is not Python 3.12"'
"$VENV_DIR/bin/python" -m pip install pip==25.0.1 setuptools==75.8.0 wheel==0.45.1
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"
"$VENV_DIR/bin/python" -m pip install --no-build-isolation --no-deps -e "$ROOT_DIR"
"$VENV_DIR/bin/python" -m pip check
