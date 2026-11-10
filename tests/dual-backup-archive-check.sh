#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="/mnt/d/Hagonoy-SMP"
WIN_TAR="/mnt/c/Windows/System32/tar.exe"

for cmd in tar sha256sum cmp; do
    command -v "$cmd" >/dev/null || {
        echo "[FAIL] Missing command: $cmd"
        exit 1
    }
done

[[ -x "$WIN_TAR" ]] || {
    echo "[FAIL] Windows tar.exe is unavailable."
    exit 1
}

TEST_ROOT="$(mktemp -d "$ROOT/.hagonoy-backup-test.XXXXXX")"
trap 'rm -rf -- "$TEST_ROOT"' EXIT

SOURCE="$TEST_ROOT/minecraft-server"
WIN_VAULT="$TEST_ROOT/windows-vault"
UBU_VAULT="$TEST_ROOT/ubuntu-vault"
RESTORE="$TEST_ROOT/restored-server"

ARCHIVE_NAME="server-backup-test.tar"
ARCHIVE="$WIN_VAULT/$ARCHIVE_NAME"
COPY="$UBU_VAULT/$ARCHIVE_NAME"

mkdir -p \
    "$SOURCE/world" \
    "$SOURCE/plugins/floodgate" \
    "$SOURCE/config" \
    "$SOURCE/logs" \
    "$SOURCE/crash-reports" \
    "$WIN_VAULT" \
    "$UBU_VAULT"

printf 'test world data\n' > "$SOURCE/world/level.dat"
printf 'test paper jar\n' > "$SOURCE/server.jar"
printf 'test geyser plugin\n' > "$SOURCE/plugins/Geyser-Spigot.jar"
printf 'test floodgate key placeholder\n' > "$SOURCE/plugins/floodgate/key.pem"
printf 'test configuration\n' > "$SOURCE/config/paper-global.yml"
printf 'test server log\n' > "$SOURCE/logs/latest.log"
printf 'test crash report\n' > "$SOURCE/crash-reports/test.txt"
printf '#!/bin/bash\necho test\n' > "$SOURCE/start.sh"
printf 'server-port=25565\n' > "$SOURCE/server.properties"

echo "========== 1. CREATE COMPLETE TAR =========="
tar -cf "$ARCHIVE" -C "$SOURCE" .
echo "[OK] Archive created."

echo
echo "========== 2. UBUNTU TAR READABILITY =========="
tar -tf "$ARCHIVE" > "$TEST_ROOT/ubuntu-list.txt"

for item in \
    "./world/level.dat" \
    "./server.jar" \
    "./plugins/Geyser-Spigot.jar" \
    "./plugins/floodgate/key.pem" \
    "./config/paper-global.yml" \
    "./logs/latest.log" \
    "./crash-reports/test.txt" \
    "./start.sh" \
    "./server.properties"
do
    grep -Fxq "$item" "$TEST_ROOT/ubuntu-list.txt" || {
        echo "[FAIL] Missing archive entry: $item"
        exit 1
    }
done

echo "[OK] World, plugins, configuration, logs and crash reports included."

echo
echo "========== 3. WINDOWS TAR READABILITY =========="
ARCHIVE_WIN="$(wslpath -w "$ARCHIVE")"
"$WIN_TAR" -tf "$ARCHIVE_WIN" > /dev/null
echo "[OK] Windows tar.exe can read the archive."

echo
echo "========== 4. COPY TO SECOND VAULT =========="
cp -- "$ARCHIVE" "$COPY"
echo "[OK] Same archive copied."

echo
echo "========== 5. SHA-256 VERIFICATION =========="
HASH_WIN="$(sha256sum "$ARCHIVE" | awk '{print $1}')"
HASH_UBU="$(sha256sum "$COPY" | awk '{print $1}')"

printf 'Windows archive: %s\n' "$HASH_WIN"
printf 'Ubuntu copy:     %s\n' "$HASH_UBU"

[[ "$HASH_WIN" == "$HASH_UBU" ]] || {
    echo "[FAIL] SHA-256 mismatch."
    exit 1
}

echo "[OK] Both archive hashes match."

echo
echo "========== 6. RESTORE TEST =========="
mkdir -p "$RESTORE"
tar -xf "$COPY" -C "$RESTORE"

cmp "$SOURCE/world/level.dat" "$RESTORE/world/level.dat"
cmp "$SOURCE/logs/latest.log" "$RESTORE/logs/latest.log"
cmp "$SOURCE/crash-reports/test.txt" "$RESTORE/crash-reports/test.txt"
cmp "$SOURCE/server.properties" "$RESTORE/server.properties"

echo "[OK] Restored files match the original fixture."

echo
echo "========== 7. ONE ARCHIVE PER VAULT =========="
[[ "$(find "$WIN_VAULT" -maxdepth 1 -type f | wc -l)" -eq 1 ]]
[[ "$(find "$UBU_VAULT" -maxdepth 1 -type f | wc -l)" -eq 1 ]]

echo "[OK] One TAR archive in each test vault."

echo
echo "========== ALL ARCHIVE TESTS PASSED =========="
