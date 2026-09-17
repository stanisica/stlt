#!/usr/bin/env bash
set -euo pipefail

JETSON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${JETSON_VENV:-$JETSON_DIR/.venv}"
PYTHON_BIN="$VENV_DIR/bin/python"
RESULTS_DIR="${JETSON_RESULTS_DIR:-$JETSON_DIR/results}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing $VENV_DIR. Run ./setup_python_env.sh first." >&2
  exit 1
fi
require_tegrastats() {
  if ! command -v tegrastats >/dev/null 2>&1; then
    echo "tegrastats is required; run this measurement on a Jetson device." >&2
    exit 1
  fi
}

mkdir -p "$RESULTS_DIR"
case "${1:-}" in
  prefix-energy)
    shift
    require_tegrastats
    RUN_ID="$(date -u +%Y%m%d_%H%M%S)"
    exec "$PYTHON_BIN" "$JETSON_DIR/prefix_energy/measure_prefix_energy.py" \
      --out "$RESULTS_DIR/prefix-energy/$RUN_ID" "$@"
    ;;
  analyze-prefix)
    if [[ $# -ne 2 ]]; then
      echo "usage: $0 analyze-prefix /path/to/prefix-run" >&2
      exit 2
    fi
    exec "$PYTHON_BIN" "$JETSON_DIR/prefix_energy/analyze_linearity.py" \
      --run "$2"
    ;;
  candidate-sets)
    shift
    require_tegrastats
    exec "$PYTHON_BIN" "$JETSON_DIR/overhead/measure_candidate_sets.py" \
      --output-dir "$RESULTS_DIR/candidate-sets" "$@"
    ;;
  scaling)
    shift
    require_tegrastats
    exec "$PYTHON_BIN" "$JETSON_DIR/overhead/measure_scaling.py" \
      --output-dir "$RESULTS_DIR/scaling" "$@"
    ;;
  *)
    echo "usage: $0 {prefix-energy|analyze-prefix|candidate-sets|scaling} [arguments]" >&2
    exit 2
    ;;
esac
