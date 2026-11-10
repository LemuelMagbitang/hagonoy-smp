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
python3 -c 'import pathlib,sys; p=pathlib.Path(sys.argv[1]); compile(p.read_text(encoding="utf-8"), str(p), "exec")' "$ROOT/bin/hagonoy-addons.py"
printf '[OK] bin/hagonoy-addons.py (Python syntax)\n'
python3 "$ROOT/tests/maintenance-tools-check.py"

