#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit the reviewed source changes before packaging." >&2
  exit 1
fi
ARCHIVE_PATH="${1:-dist/stlt-artifact.tar.gz}"
if [[ -e "$ARCHIVE_PATH" ]]; then
  echo "Archive already exists: $ARCHIVE_PATH" >&2
  exit 1
fi
mkdir -p "$(dirname "$ARCHIVE_PATH")"
git archive --format=tar.gz --prefix=stlt-artifact/ --output="$ARCHIVE_PATH" HEAD
python3.12 -c 'import hashlib, pathlib, sys; p = pathlib.Path(sys.argv[1]); print(hashlib.sha256(p.read_bytes()).hexdigest(), p)' "$ARCHIVE_PATH" > "$ARCHIVE_PATH.sha256"
git rev-parse HEAD > "$ARCHIVE_PATH.commit"
cat "$ARCHIVE_PATH.sha256"
