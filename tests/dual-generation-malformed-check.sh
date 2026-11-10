#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/bin/hagonoy-generation"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEST_ROOT"' EXIT

BASE="$TEST_ROOT/base"
mkdir -p "$BASE"
"$HELPER" seal "$BASE" ubuntu "Paper-test" "MC-test" >/dev/null

expect_rejected() {
    local name="$1"
    local payload="$2"
    local dir="$TEST_ROOT/$name"

    mkdir -p "$dir"
    printf '%s\n' "$payload" > "$dir/.hagonoy-generation.json"

    if "$HELPER" show "$dir" >"$TEST_ROOT/out" 2>&1; then
        echo "[FAIL] Accepted malformed manifest: $name"
        exit 1
    fi

    echo "[OK] Rejected malformed manifest: $name"
}

expect_rejected "non-object" '[]'
expect_rejected "boolean-schema" '{"schema_version":true}'
expect_rejected "boolean-generation" '{"schema_version":1,"state":"stopped","generation":true,"generation_id":"x","ancestors":[]}'
expect_rejected "missing-ancestry" '{"schema_version":1,"state":"stopped","generation":2,"generation_id":"x","parent_generation_id":"p"}'
expect_rejected "duplicate-ancestors" '{"schema_version":1,"state":"stopped","generation":3,"generation_id":"x","parent_generation_id":"p","ancestors":["p","p"]}'
expect_rejected "wrong-parent" '{"schema_version":1,"state":"stopped","generation":2,"generation_id":"x","parent_generation_id":"wrong","ancestors":["p"]}'
expect_rejected "self-ancestor" '{"schema_version":1,"state":"stopped","generation":2,"generation_id":"x","parent_generation_id":"x","ancestors":["x"]}'

echo
echo "========== ALL MALFORMED-MANIFEST TESTS PASSED =========="
