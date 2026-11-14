#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
while IFS= read -r -d '' file; do
    bash -n "$file"
    printf '[OK] %s\n' "${file#"$ROOT"/}"
done < <(find "$ROOT" -type f -name '*.sh' -print0)
bash -n "$ROOT/bin/hagonoy"
printf '[OK] bin/hagonoy\n'
bash -n "$ROOT/hagonoy"
printf '[OK] hagonoy\n'
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding="utf-8"), str(p), "exec")' "$ROOT/bin/hagonoy-world-border.py"
printf '[OK] bin/hagonoy-world-border.py (Python syntax)\n'
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding="utf-8"), str(p), "exec")' "$ROOT/bin/hagonoy_chunky_pregen.py"
printf '[OK] bin/hagonoy_chunky_pregen.py (Python syntax)\n'
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding="utf-8"), str(p), "exec")' "$ROOT/bin/hagonoy-addons.py"
printf '[OK] bin/hagonoy-addons.py (Python syntax)\n'
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding="utf-8"), str(p), "exec")' "$ROOT/bin/hagonoy-generation"
printf '[OK] bin/hagonoy-generation (Python syntax)\n'
bash -n "$ROOT/bin/hagonoy-dual-core-update"
printf '[OK] bin/hagonoy-dual-core-update (shell syntax)\n'
python3 "$ROOT/tests/dual-runtime-version-probe-check.py"
python3 "$ROOT/tests/dual-geyser-download-key-check.py"
python3 "$ROOT/tests/dual-host-routing-check.py"
python3 "$ROOT/tests/dual-host-core-route-check.py"
python3 "$ROOT/tests/dual-core-update-cache-check.py"
bash "$ROOT/tests/dual-core-update-api-check.sh"
bash "$ROOT/tests/dual-core-update-plan-check.sh"
bash "$ROOT/tests/dual-core-update-execution-check.sh"
bash "$ROOT/tests/dual-paper-update-api-check.sh"
bash "$ROOT/tests/dual-paper-update-plan-check.sh"
bash "$ROOT/tests/dual-paper-update-execution-check.sh"

python3 "$ROOT/tests/world-border-sync-check.py"
python3 "$ROOT/tests/chunky-border-pregen-check.py"
python3 "$ROOT/tests/maintenance-tools-check.py"

