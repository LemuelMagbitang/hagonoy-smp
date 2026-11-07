#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_ROOT"' EXIT

MOCK_BIN="$TEMP_ROOT/mock-bin"
LIVE_DIR="$TEMP_ROOT/live-server"
BACKUP_DIR="$TEMP_ROOT/backups"
TMUX_LOG="$TEMP_ROOT/tmux.log"
SYSTEMCTL_LOG="$TEMP_ROOT/systemctl.log"
mkdir -p "$MOCK_BIN" "$LIVE_DIR" "$BACKUP_DIR"
: > "$TMUX_LOG"
: > "$SYSTEMCTL_LOG"

cat > "$MOCK_BIN/tmux" <<'MOCK'
#!/usr/bin/env bash
case "${1:-}" in
    has-session)
        [[ "${MOCK_HAGONOY_SESSION_ACTIVE:-false}" == "true" ]]
        ;;
    new-session)
        printf '%s\n' "$*" >> "$MOCK_TMUX_LOG"
        exit 0
        ;;
    send-keys)
        printf '%s\n' "$*" >> "$MOCK_TMUX_LOG"
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
MOCK

cat > "$MOCK_BIN/ss" <<'MOCK'
#!/usr/bin/env bash
exit 0
MOCK

cat > "$MOCK_BIN/systemctl" <<'MOCK'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$MOCK_SYSTEMCTL_LOG"
if [[ "${1:-}" == "is-active" && "${2:-}" == "--quiet" && "${3:-}" == "playit.service" ]]; then
    [[ "${MOCK_PLAYIT_SERVICE_ACTIVE:-false}" == "true" ]]
    exit $?
fi
exit 1
MOCK

cat > "$MOCK_BIN/pgrep" <<'MOCK'
#!/usr/bin/env bash
if [[ "${1:-}" == "-x" && "${2:-}" == "playitd" ]]; then
    [[ "${MOCK_PLAYIT_PROCESS_ACTIVE:-false}" == "true" ]]
    exit $?
fi
if [[ "${1:-}" == "-x" && "${2:-}" == "playit" ]]; then
    exit 1
fi
exit 1
MOCK
chmod +x "$MOCK_BIN"/*

cat > "$TEMP_ROOT/manager.conf" <<CONFIG
MC_DIR="$LIVE_DIR"
TMUX_SESSION="mcserver"
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
PLAYIT_SESSION="playit-tunnel"
PLAYIT_STOP_WITH_SERVER="false"
CONFIG

run_hagonoy() {
    PATH="$MOCK_BIN:$PATH" \
    HAGONOY_CONFIG="$TEMP_ROOT/manager.conf" \
    MOCK_TMUX_LOG="$TMUX_LOG" \
    MOCK_SYSTEMCTL_LOG="$SYSTEMCTL_LOG" \
    "$ROOT/hagonoy" "$@"
}

# A Playit systemd service is shown as running.
STATUS="$(MOCK_PLAYIT_SERVICE_ACTIVE=true run_hagonoy status)"
grep -Fq 'Playit agent:      RUNNING (systemd service)' <<< "$STATUS"
printf '[OK] Status detects active Playit systemd service\n'

# Starting Playit must not launch a duplicate tmux agent.
OUTPUT="$(MOCK_PLAYIT_SERVICE_ACTIVE=true run_hagonoy playit-start)"
grep -Fq 'not starting a duplicate agent' <<< "$OUTPUT"
! grep -Fq 'new-session' "$TMUX_LOG"
printf '[OK] playit-start avoids duplicating the systemd agent\n'

# Hagonoy must not pretend it can stop a system-managed agent.
if MOCK_PLAYIT_SERVICE_ACTIVE=true run_hagonoy playit-stop >/dev/null 2>&1; then
    printf '[FAIL] playit-stop unexpectedly reported success for a systemd agent\n' >&2
    exit 1
fi
if grep -Eq '^stop playit(\.service)?$' "$SYSTEMCTL_LOG"; then
    printf '[FAIL] Hagonoy unexpectedly attempted to stop the system service\n' >&2
    exit 1
fi
printf '[OK] playit-stop refuses to control the systemd agent\n'

# A separately launched playitd process is also detected.
STATUS="$(MOCK_PLAYIT_PROCESS_ACTIVE=true run_hagonoy status)"
grep -Fq 'Playit agent:      RUNNING (external process)' <<< "$STATUS"
printf '[OK] Status detects an external Playit process\n'

# When no service/process is active, manual start uses Hagonoy's tmux session.
: > "$TMUX_LOG"
OUTPUT="$(run_hagonoy playit-start)"
grep -Fq "Starting Playit in tmux session 'playit-tunnel'" <<< "$OUTPUT"
grep -Fq 'new-session' "$TMUX_LOG"
printf '[OK] Manual start uses tmux when no Playit agent is active\n'
