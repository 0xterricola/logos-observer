#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
OUTPUT="${1:-/tmp/observer-release-candidate.lgx}"
WORK="$(mktemp -d "${TMPDIR:-/tmp/}logos-package.XXXXXX")"

trap 'rm -rf "$WORK"' EXIT

echo "=== BUILD PORTABLE MODULE ==="
nix build -L "$ROOT/integrations/basecamp#lgx-portable" \
  --out-link "$WORK/built"

SOURCE="$WORK/built/logos-observer-module-lib.lgx"
REPAIRED="$WORK/repaired.lgx"

echo "=== REPAIR MACH-O DEPENDENCIES ==="
"$ROOT/integrations/basecamp/scripts/repair-lgx-macos.sh" \
  "$SOURCE" "$REPAIRED"

echo "=== REGENERATE CONTENT HASHES ==="
mkdir -p "$WORK/extracted"
tar -xzf "$REPAIRED" -C "$WORK/extracted"

mkdir -p "$(dirname "$OUTPUT")"
cp "$REPAIRED" "$OUTPUT"

nix run github:logos-co/logos-package#lgx -- \
  add "$OUTPUT" \
  --variant darwin-arm64 \
  --files "$WORK/extracted/variants/darwin-arm64" \
  --main observer_plugin.dylib \
  -y

echo "=== VERIFY FINAL PACKAGE ==="
nix run github:logos-co/logos-package#lgx -- \
  verify "$OUTPUT"

echo "=== PORTABLE RUNTIME SMOKE TEST ==="
(
  set -euo pipefail

  TEST="$WORK/smoke"
  mkdir -p "$TEST"
  tar -xzf "$OUTPUT" -C "$TEST"

  BIN="$TEST/assets/lidl/observer-runtime/portable-macos-arm64/observer"
  test -x "$BIN"

  echo "=== BUNDLED PAIRING CLI SMOKE TEST ==="
  PAIR_HELP="$("$BIN" pair --help)"
  grep -q -- '--json' <<< "$PAIR_HELP"
  grep -q -- '--existing-identity' <<< "$PAIR_HELP"
  echo "PASS: Bundled pairing CLI"

  PORT="$(python3 - <<'PYPORT'
import socket
with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PYPORT
)"

  env -i \
    HOME="$TEST" \
    PATH="/usr/bin:/bin" \
    TMPDIR="${TMPDIR:-/tmp/}" \
    "$BIN" \
      --host 127.0.0.1 \
      --port "$PORT" \
      --state-dir "$TEST/state" \
      > "$TEST/observer.log" 2>&1 &

  PID=$!
  trap 'kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true' EXIT

  HEALTH=000
  for ((i=0; i<40; i++)); do
    HEALTH="$(curl -ks --max-time 2 -o /dev/null \
      -w '%{http_code}' "https://127.0.0.1:$PORT/health" || true)"

    [[ "$HEALTH" == "200" ]] && break
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.5
  done

  AUTH="$(curl -ks --max-time 3 -o /dev/null \
    -w '%{http_code}' "https://127.0.0.1:$PORT/v2/status" || true)"

  echo "Health: HTTP $HEALTH"
  echo "Authentication: HTTP $AUTH"

  if [[ "$HEALTH" != "200" || "$AUTH" != "401" ]]; then
    echo "FAIL: Portable runtime smoke test"
    tail -40 "$TEST/observer.log"
    exit 1
  fi

  echo "PASS: Portable runtime smoke test"
)

echo "=== PACKAGE READY ==="
ls -lh "$OUTPUT"
