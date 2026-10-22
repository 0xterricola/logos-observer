#!/usr/bin/env bash
set -euo pipefail

INPUT="${1:?Usage: repair-lgx-macos.sh input.lgx output.lgx}"
OUTPUT="${2:?Output .lgx path required}"

if [[ "$INPUT" == "$OUTPUT" ]]; then
  echo "Input and output must be different" >&2
  exit 1
fi

WORK="$(mktemp -d "${TMPDIR:-/tmp/}observer-lgx-repair.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

tar -xzf "$INPUT" -C "$WORK"

RUNTIME="$WORK/assets/lidl/observer-runtime/portable-macos-arm64"

python3 - "$RUNTIME" <<'PY'
import os
import subprocess
import sys
from pathlib import Path

runtime = Path(sys.argv[1])
internal = runtime / "_internal"

libs = {
    name: internal / name
    for name in ("libssl.3.dylib", "libcrypto.3.dylib")
}

for lib in libs.values():
    if not lib.is_file():
        raise SystemExit(f"Missing bundled library: {lib}")

changed = set()

for binary in sorted(runtime.rglob("*")):
    if not binary.is_file() or binary.is_symlink():
        continue
    if binary.suffix not in (".so", ".dylib"):
        continue

    result = subprocess.run(
        ["otool", "-L", str(binary)],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        continue

    for line in result.stdout.splitlines()[1:]:
        ref = line.strip().split(" (", 1)[0]
        target = libs.get(ref.rsplit("/", 1)[-1])

        if target is None or binary == target:
            continue

        relative = os.path.relpath(target, binary.parent)
        desired = "@loader_path/" + relative

        if ref != desired:
            subprocess.run(
                ["install_name_tool", "-change", ref, desired, str(binary)],
                check=True
            )
            changed.add(binary)

for name, binary in libs.items():
    desired_id = "@rpath/" + name
    current = subprocess.run(
        ["otool", "-D", str(binary)],
        capture_output=True,
        text=True,
        check=True
    ).stdout.splitlines()

    current_id = current[1].strip() if len(current) > 1 else ""

    if current_id != desired_id:
        subprocess.run(
            ["install_name_tool", "-id", desired_id, str(binary)],
            check=True
        )
        changed.add(binary)

for binary in sorted(changed):
    subprocess.run(
        ["codesign", "--force", "--sign", "-", str(binary)],
        check=True
    )
    print("Repaired:", binary.relative_to(runtime))

print(f"Re-signed {len(changed)} binaries")
PY

mkdir -p "$(dirname "$OUTPUT")"
tar -czf "$OUTPUT" -C "$WORK" manifest.json variants assets

echo "=== REPAIRED PACKAGE ==="
file "$OUTPUT"
du -h "$OUTPUT"
