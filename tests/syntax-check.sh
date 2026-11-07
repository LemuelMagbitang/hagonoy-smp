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
