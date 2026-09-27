#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit the reviewed source changes before packaging." >&2
  exit 1
fi
ARCHIVE_PATH="${1:-dist/stlt-artifact.tar.gz}"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_COMMAND="$PYTHON"
elif [[ -x "$ROOT_DIR/.stlt-venv/bin/python" ]]; then
  PYTHON_COMMAND="$ROOT_DIR/.stlt-venv/bin/python"
else
  PYTHON_COMMAND="python3.12"
fi
"$PYTHON_COMMAND" - "$ARCHIVE_PATH" <<'PY'
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile

if sys.version_info[:2] != (3, 12):
    raise SystemExit("Python 3.12 is required")

archive = Path(sys.argv[1])
targets = [archive, Path(f"{archive}.sha256"), Path(f"{archive}.commit")]
published = []
try:
    for target in targets:
        if os.path.lexists(target):
            raise FileExistsError(f"Package file already exists: {target}")
    revision = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    archive.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".stlt-package-", dir=archive.parent) as directory:
        staged = [Path(directory) / str(index) for index in range(3)]
        subprocess.run(
            [
                "git", "archive", "--format=tar.gz", "--prefix=stlt-artifact/",
                f"--output={staged[0]}", revision,
            ],
            check=True,
        )
        with staged[0].open("rb") as stream:
            checksum = hashlib.file_digest(stream, "sha256").hexdigest()
        checksum_line = f"{checksum}  {archive}\n"
        staged[1].write_text(checksum_line)
        staged[2].write_text(revision + "\n")
        for source, target in zip(staged, targets):
            os.link(source, target)
            published.append(target)
except (OSError, subprocess.CalledProcessError, KeyboardInterrupt) as error:
    for target in reversed(published):
        target.unlink()
    raise SystemExit(f"Packaging failed: {error}") from error
print(checksum_line, end="")
PY
