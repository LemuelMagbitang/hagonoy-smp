#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/mnt/d/Hagonoy-SMP"
TEST_ROOT="$(mktemp -d "$ROOT/.hagonoy-promotion-test.XXXXXX")"
trap 'rm -rf -- "$TEST_ROOT"' EXIT

promote() {
    local stage="$1" dest="$2" rollback="$3" expected="$4"
    local failed="${dest}.failed"

    [[ -d "$stage" ]] || return 1
    [[ ! -e "$rollback" && ! -e "$failed" ]] || return 1

    if [[ -e "$dest" ]]; then
        mv -- "$dest" "$rollback" || return 1
    fi

    if ! mv -- "$stage" "$dest"; then
        [[ ! -e "$dest" && -d "$rollback" ]] &&
            mv -- "$rollback" "$dest"
        return 1
    fi

    local actual
    actual="$(sha256sum "$dest/release.txt" | awk '{print $1}')"

    if [[ "$actual" != "$expected" ]]; then
        mv -- "$dest" "$failed"
        if [[ -d "$rollback" ]]; then
            mv -- "$rollback" "$dest"
        fi
        return 1
    fi

    return 0
}

echo "========== 1. SUCCESSFUL PROMOTION =========="

mkdir -p "$TEST_ROOT/current" "$TEST_ROOT/incoming"
printf 'old generation\n' > "$TEST_ROOT/current/release.txt"
printf 'new generation\n' > "$TEST_ROOT/incoming/release.txt"

EXPECTED="$(sha256sum "$TEST_ROOT/incoming/release.txt" | awk '{print $1}')"

promote "$TEST_ROOT/incoming" "$TEST_ROOT/current" \
    "$TEST_ROOT/rollback" "$EXPECTED"

grep -Fxq 'new generation' "$TEST_ROOT/current/release.txt"
grep -Fxq 'old generation' "$TEST_ROOT/rollback/release.txt"

echo "[OK] New directory promoted; previous copy retained."

echo
echo "========== 2. FAILED VERIFICATION / ROLLBACK =========="

mkdir -p "$TEST_ROOT/incoming-failed"
printf 'corrupted generation\n' > "$TEST_ROOT/incoming-failed/release.txt"

OLD_HASH="$(sha256sum "$TEST_ROOT/current/release.txt" | awk '{print $1}')"

if promote "$TEST_ROOT/incoming-failed" "$TEST_ROOT/current" \
    "$TEST_ROOT/rollback-2" "intentionally-wrong-hash"; then
    echo "[FAIL] Invalid incoming copy was accepted."
    exit 1
fi

RESTORED_HASH="$(sha256sum "$TEST_ROOT/current/release.txt" | awk '{print $1}')"

[[ "$OLD_HASH" == "$RESTORED_HASH" ]]
grep -Fxq 'new generation' "$TEST_ROOT/current/release.txt"
[[ -d "$TEST_ROOT/current.failed" ]]

echo "[OK] Failed incoming copy rejected."
echo "[OK] Previous destination restored."
echo "[OK] Failed copy retained for inspection."

echo
echo "========== 3. MISSING STAGE PROTECTION =========="

if promote "$TEST_ROOT/does-not-exist" "$TEST_ROOT/current" \
    "$TEST_ROOT/rollback-3" "$EXPECTED"; then
    echo "[FAIL] Missing staging directory was accepted."
    exit 1
fi

grep -Fxq 'new generation' "$TEST_ROOT/current/release.txt"
echo "[OK] Missing stage rejected; current copy unchanged."

echo
echo "========== ALL PROMOTION TESTS PASSED =========="
