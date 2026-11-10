#!/usr/bin/env bash
set -Eeuo pipefail

source "$(dirname "$0")/../config/dual-host.conf"

SSH=(ssh -o BatchMode=yes -o ConnectTimeout=8)
TEST_ROOT="$(mktemp -d /mnt/d/Hagonoy-SMP/.hagonoy-transfer-test.XXXXXX)"
REMOTE_FILE="/tmp/hagonoy-transfer-test-${USER}-$$.tar"

cleanup() {
    "${SSH[@]}" "$UBUNTU_SSH_TARGET" \
        "rm -f -- '$REMOTE_FILE'" >/dev/null 2>&1 || true
    rm -rf -- "$TEST_ROOT"
}
trap cleanup EXIT

mkdir -p "$TEST_ROOT/source/world" "$TEST_ROOT/source/logs"

printf 'World transfer test\n' > "$TEST_ROOT/source/world/level.dat"
printf 'Log transfer test\n' > "$TEST_ROOT/source/logs/latest.log"

ARCHIVE="$TEST_ROOT/server-backup-test.tar"

echo "========== 1. CREATE TEST ARCHIVE =========="
tar -cf "$ARCHIVE" -C "$TEST_ROOT/source" .
echo "[OK] Archive created."

LOCAL_HASH="$(sha256sum "$ARCHIVE" | awk '{print $1}')"

echo
echo "========== 2. TRANSFER THROUGH SSH/RSYNC =========="
rsync -t --info=progress2 \
    -e 'ssh -o BatchMode=yes -o ConnectTimeout=8' \
    "$ARCHIVE" \
    "$UBUNTU_SSH_TARGET:$REMOTE_FILE"

echo "[OK] Archive transferred."

echo
echo "========== 3. REMOTE TAR VERIFICATION =========="
"${SSH[@]}" "$UBUNTU_SSH_TARGET" \
    "tar -tf '$REMOTE_FILE' >/dev/null"
echo "[OK] Ubuntu can read the transferred archive."

echo
echo "========== 4. REMOTE SHA-256 =========="
REMOTE_HASH="$("${SSH[@]}" "$UBUNTU_SSH_TARGET" \
    "sha256sum '$REMOTE_FILE' | awk '{print \$1}'")"

printf 'WSL archive:    %s\n' "$LOCAL_HASH"
printf 'Ubuntu archive: %s\n' "$REMOTE_HASH"

[[ "$LOCAL_HASH" == "$REMOTE_HASH" ]] || {
    echo "[FAIL] SHA-256 mismatch."
    exit 1
}

echo "[OK] Remote and local SHA-256 match."

echo
echo "========== ALL SSH TRANSFER TESTS PASSED =========="
