#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/common.sh"
"$PYTHON_BIN" -m pip check
"$PYTHON_BIN" -m stlt_artifact.cli check
"$PYTHON_BIN" -m unittest discover -s "$ROOT_DIR/tests" -v
