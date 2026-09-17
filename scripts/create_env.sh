#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$ROOT_DIR/.stlt-venv"

if [[ -e "$VENV_DIR" ]]; then
  echo "Environment already exists: $VENV_DIR"
  exit 0
fi

python3.12 -m venv "$VENV_DIR"
"$VENV_DIR/bin/python" -m pip install --upgrade pip
"$VENV_DIR/bin/python" -m pip install -e "$ROOT_DIR"

