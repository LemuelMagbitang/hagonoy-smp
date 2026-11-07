#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_ROOT"' EXIT

MOCK_BIN="$TEMP_ROOT/mock-bin"
FIXTURE="$TEMP_ROOT/fixture"
LIVE_DIR="$TEMP_ROOT/live-server"
BACKUP_DIR="$TEMP_ROOT/backups"
mkdir -p "$MOCK_BIN" "$FIXTURE" "$LIVE_DIR" "$BACKUP_DIR"

cat > "$MOCK_BIN/tmux" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == "has-session" && "${MOCK_MINECRAFT_RUNNING:-false}" == "true" ]]; then
    exit 0
fi
exit 1
MOCK

cat > "$MOCK_BIN/ss" <<'MOCK'
#!/usr/bin/env bash
if [[ "${MOCK_PORT_OPEN:-false}" == "true" ]]; then
    printf 'LISTEN 0 4096 0.0.0.0:25565 0.0.0.0:*\n'
fi
exit 0
MOCK
chmod +x "$MOCK_BIN/tmux" "$MOCK_BIN/ss"

printf 'test server settings\n' > "$FIXTURE/server.properties"
cat > "$FIXTURE/start.sh" <<'START'
#!/usr/bin/env bash
exit 0
START
chmod +x "$FIXTURE/start.sh"

cat > "$TEMP_ROOT/manager.conf" <<CONFIG
MC_DIR="$LIVE_DIR"
TMUX_SESSION="restore-test"
START_COMMAND="./start.sh"
MINECRAFT_PORT="25565"
SERVER_LOG="logs/latest.log"
READY_PATTERN="Done"
START_TIMEOUT_SECONDS="30"
STOP_TIMEOUT_SECONDS="30"
BACKUP_DIR="$BACKUP_DIR"
BACKUP_RETENTION="2"
PLAYIT_AUTO_START="false"
PLAYIT_COMMAND="playit"
PLAYIT_SESSION="playit-test"
PLAYIT_STOP_WITH_SERVER="false"
CONFIG

ARCHIVE="$BACKUP_DIR/hagonoy-smp-test.tar"
tar -cf "$ARCHIVE" -C "$FIXTURE" .

run_restore() {
    PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$TEMP_ROOT/manager.conf" \
        "$ROOT/hagonoy" restore "$@" >/dev/null 2>&1
}

# Successful restore into a new directory.
GOOD_DEST="$TEMP_ROOT/restored-server"
run_restore "$ARCHIVE" "$GOOD_DEST"
[[ -f "$GOOD_DEST/server.properties" && -x "$GOOD_DEST/start.sh" ]]
printf '[OK] Valid archive restores into a new destination\n'

# Existing destination must remain untouched.
EXISTING_DEST="$TEMP_ROOT/existing-server"
mkdir "$EXISTING_DEST"
printf 'keep this file\n' > "$EXISTING_DEST/marker"
if run_restore "$ARCHIVE" "$EXISTING_DEST"; then
    printf '[FAIL] Existing destination was unexpectedly accepted\n' >&2
    exit 1
fi
[[ "$(cat "$EXISTING_DEST/marker")" == "keep this file" ]]
printf '[OK] Existing destination is refused and preserved\n'

# Refuse restore while the managed server session is active.
RUNNING_DEST="$TEMP_ROOT/running-server"
if MOCK_MINECRAFT_RUNNING=true PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$TEMP_ROOT/manager.conf" \
    "$ROOT/hagonoy" restore "$ARCHIVE" "$RUNNING_DEST" >/dev/null 2>&1; then
    printf '[FAIL] Restore was unexpectedly allowed while Minecraft was running\n' >&2
    exit 1
fi
[[ ! -e "$RUNNING_DEST" ]]
printf '[OK] Running Minecraft session blocks restore\n'

# Refuse restore while the configured server port is listening.
PORT_DEST="$TEMP_ROOT/port-server"
if MOCK_PORT_OPEN=true PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$TEMP_ROOT/manager.conf" \
    "$ROOT/hagonoy" restore "$ARCHIVE" "$PORT_DEST" >/dev/null 2>&1; then
    printf '[FAIL] Restore was unexpectedly allowed while the server port was open\n' >&2
    exit 1
fi
[[ ! -e "$PORT_DEST" ]]
printf '[OK] Listening Minecraft port blocks restore\n'

# Refuse archive member paths that attempt to escape the extraction directory.
mkdir "$TEMP_ROOT/unsafe-source"
printf 'outside\n' > "$TEMP_ROOT/escape.txt"
UNSAFE_ARCHIVE="$BACKUP_DIR/hagonoy-smp-unsafe.tar"
tar -P -cf "$UNSAFE_ARCHIVE" -C "$TEMP_ROOT/unsafe-source" ../escape.txt
UNSAFE_DEST="$TEMP_ROOT/unsafe-server"
if run_restore "$UNSAFE_ARCHIVE" "$UNSAFE_DEST"; then
    printf '[FAIL] Unsafe archive path was unexpectedly accepted\n' >&2
    exit 1
fi
[[ ! -e "$UNSAFE_DEST" ]]
printf '[OK] Unsafe archive member path is refused\n'
