#!/usr/bin/env bash
set -euo pipefail

JETSON_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${JETSON_VENV:-$JETSON_DIR/.venv}"

if [[ ! -d "$VENV_DIR" ]]; then
  python3 -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip wheel
"$VENV_DIR/bin/python" -m pip install \
  --index-url https://download.pytorch.org/whl/cpu \
  torch==2.12.0+cpu torchvision==0.27.0+cpu
"$VENV_DIR/bin/python" -m pip install fvcore matplotlib==3.10.0

"$VENV_DIR/bin/python" - <<'PY'
import platform
import torch
import torchvision

print("machine:", platform.machine())
print("python:", platform.python_version())
print("torch:", torch.__version__)
print("torchvision:", torchvision.__version__)
print("CUDA enabled:", torch.cuda.is_available())
PY

echo "Jetson measurement environment: $VENV_DIR"
