#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
OUT="$ROOT/integrations/basecamp/.portable-build/macos-arm64"
PYTHON="$ROOT/.venv/bin/python"

if [[ "$(uname -s)" != "Darwin" || "$(uname -m)" != "arm64" ]]; then
  echo "This build currently supports macOS ARM64 only." >&2
  exit 1
fi

"$PYTHON" -m PyInstaller \
  --noconfirm \
  --clean \
  --onedir \
  --name logos-observer \
  --target-arch arm64 \
  --paths "$ROOT/integrations/basecamp/runtime" \
  --distpath "$OUT/dist" \
  --workpath "$OUT/work" \
  --specpath "$OUT/spec" \
  "$ROOT/integrations/basecamp/runtime/v2_server.py"

BUNDLE="$OUT/dist/logos-observer"

echo "=== PORTABLE EXECUTABLE ==="
file "$BUNDLE/logos-observer"

echo "=== BUNDLE SIZE ==="
du -sh "$BUNDLE"

echo "=== BUNDLE CONTENTS ==="
ls -la "$BUNDLE"

echo "Portable bundle: $BUNDLE"
