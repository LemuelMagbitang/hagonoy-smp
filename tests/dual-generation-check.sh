#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT/bin/hagonoy-generation"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEST_ROOT"' EXIT

U="$TEST_ROOT/ubuntu"
W="$TEST_ROOT/windows"
mkdir -p "$U" "$W"

echo "========== 1. INITIAL GENERATION =========="
"$HELPER" seal "$U" ubuntu "Paper-test" "MC-test" >/dev/null
cp "$U/.hagonoy-generation.json" "$W/"
"$HELPER" select "$U" "$W" | grep -q 'EQUAL=SHARED_GENERATION'
echo "[OK] Shared generation identity recognized."

echo
echo "========== 2. DIVERGENT BRANCHES =========="
"$HELPER" begin "$U" ubuntu "Paper-test" "MC-test" >/dev/null
"$HELPER" finish "$U" >/dev/null
"$HELPER" begin "$W" windows "Paper-test" "MC-test" >/dev/null
"$HELPER" finish "$W" >/dev/null

if "$HELPER" select "$U" "$W" >"$TEST_ROOT/out" 2>&1; then
    echo "[FAIL] Divergent generations were accepted."
    exit 1
fi
grep -q "Generation conflict" "$TEST_ROOT/out"
echo "[OK] Divergent branches rejected."

echo
echo "========== 3. HIGHER NUMBER WITHOUT DESCENT =========="
"$HELPER" begin "$U" ubuntu "Paper-test" "MC-test" >/dev/null
"$HELPER" finish "$U" >/dev/null

if "$HELPER" select "$U" "$W" >"$TEST_ROOT/out" 2>&1; then
    echo "[FAIL] Unrelated higher generation was accepted."
    exit 1
fi
grep -q "does not prove descent" "$TEST_ROOT/out"
echo "[OK] Higher but unrelated generation rejected."

echo
echo "========== 4. VALID DESCENDANT =========="
cp "$U/.hagonoy-generation.json" "$W/"
"$HELPER" begin "$W" windows "Paper-test" "MC-test" >/dev/null
"$HELPER" finish "$W" >/dev/null
"$HELPER" select "$U" "$W" | grep -q 'WINNER=WINDOWS'
echo "[OK] Proven descendant selected."

echo
echo "========== 5. RUNNING GENERATION =========="
"$HELPER" begin "$W" windows "Paper-test" "MC-test" >/dev/null

if "$HELPER" select "$U" "$W" >"$TEST_ROOT/out" 2>&1; then
    echo "[FAIL] Running generation was accepted."
    exit 1
fi
grep -q "RUNNING" "$TEST_ROOT/out"
echo "[OK] Running generation rejected."

echo
echo "========== ALL GENERATION TESTS PASSED =========="
