#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "$0")/.." && pwd)"
for cmd in jq python3 sha256sum tar df stat; do
    command -v "$cmd" >/dev/null 2>&1 || {
        printf '[SKIP] Required test dependency missing: %s\n' "$cmd"
        exit 0
    }
done

TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf -- "$TEMP_ROOT"' EXIT
MOCK_BIN="$TEMP_ROOT/mock-bin"
mkdir -p "$MOCK_BIN"

cat > "$MOCK_BIN/curl" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
output=""
while (($#)); do
    if [[ "$1" == "--output" ]]; then
        output="$2"
        shift 2
    else
        shift
    fi
done
if [[ -n "$output" ]]; then
    cp -- "$MOCK_DOWNLOAD_FILE" "$output"
else
    cat -- "$MOCK_API_RESPONSE"
fi
MOCK

cat > "$MOCK_BIN/tmux" <<'MOCK'
#!/usr/bin/env bash
set -Eeuo pipefail
case "$1" in
    has-session)
        [[ -f "$MOCK_STATE_FILE" ]]
        ;;
    new-session)
        touch "$MOCK_STATE_FILE"
        current_sha="$(sha256sum "$MOCK_MC_DIR/server.jar" | awk '{print $1}')"
        if [[ "$current_sha" == "$MOCK_NEW_SHA" ]]; then
            build="$MOCK_NEW_BUILD"
        else
            build="$MOCK_OLD_BUILD"
        fi
        printf '[15:00:00] [Server thread/INFO]: Starting minecraft server version %s\n' "$MOCK_MC_VERSION" >> "$MOCK_MC_DIR/logs/latest.log"
        printf '[15:00:01] [Server thread/INFO]: This server is running Paper version %s-%s-ver/%s@mock (2026-11-07T00:00:00Z) (Implementing API version %s.build.%s-stable)\n' \
            "$MOCK_MC_VERSION" "$build" "$MOCK_MC_VERSION" "$MOCK_MC_VERSION" "$build" >> "$MOCK_MC_DIR/logs/latest.log"
        if [[ "$MOCK_FAIL_NEW" != "true" || "$build" != "$MOCK_NEW_BUILD" ]]; then
            printf '[15:00:02] [Server thread/INFO]: Done (mock)! For help, type "help"\n' >> "$MOCK_MC_DIR/logs/latest.log"
        fi
        ;;
    send-keys)
        if [[ "$4" == "stop" ]]; then
            rm -f -- "$MOCK_STATE_FILE"
        fi
        ;;
    *)
        exit 0
        ;;
esac
MOCK

cat > "$MOCK_BIN/ss" <<'MOCK'
#!/usr/bin/env bash
if [[ -f "$MOCK_STATE_FILE" ]]; then
    printf 'LISTEN 0 4096 0.0.0.0:25565 0.0.0.0:*\n'
fi
MOCK
chmod +x "$MOCK_BIN/curl" "$MOCK_BIN/tmux" "$MOCK_BIN/ss"

make_jar() {
    local build="$1"
    local output="$2"
    python3 - "$build" "$output" <<'PY'
import sys
import zipfile

build, output = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n\n")
    archive.writestr("build-marker.txt", f"Paper test build {build}\n")
PY
}

run_scenario() {
    local name="$1"
    local fail_new="$2"
    local scenario="$TEMP_ROOT/$name"
    local mc_dir="$scenario/minecraft-server"
    local backup_dir="$scenario/backups"
    local fixture_dir="$scenario/fixtures"
    local old_jar="$fixture_dir/old.jar"
    local new_jar="$fixture_dir/new.jar"
    local state_file="$scenario/server.running"
    local api_response="$scenario/paper-api.json"
    local old_sha new_sha new_size index backup_fixture jar_fixture
    mkdir -p "$mc_dir/logs" "$backup_dir" "$fixture_dir"

    # Seed older recovery artifacts. Successful updates must not prune them.
    for index in 1 2 3 4; do
        backup_fixture="$backup_dir/hagonoy-smp-2020010${index}-000000.tar"
        tar -cf "$backup_fixture" --files-from /dev/null
        jar_fixture="$mc_dir/server.jar.previous-2020010${index}-000000-build$((50 + index))"
        : > "$jar_fixture"
    done

    make_jar 61 "$old_jar"
    make_jar 74 "$new_jar"
    cp -- "$old_jar" "$mc_dir/server.jar"
    old_sha="$(sha256sum "$old_jar" | awk '{print $1}')"
    new_sha="$(sha256sum "$new_jar" | awk '{print $1}')"
    new_size="$(stat -c '%s' "$new_jar")"

    cat > "$mc_dir/start.sh" <<'START'
#!/usr/bin/env bash
java -Xms512M -Xmx1024M -jar server.jar nogui
START
    chmod +x "$mc_dir/start.sh"
    printf 'server-port=25565\n' > "$mc_dir/server.properties"
    printf '[15:00:00] [Server thread/INFO]: Starting minecraft server version 26.1.2\n' > "$mc_dir/logs/latest.log"
    printf '[15:00:01] [Server thread/INFO]: This server is running Paper version 26.1.2-61-ver/26.1.2@old (2026-11-01T00:00:00Z) (Implementing API version 26.1.2.build.61-stable)\n' >> "$mc_dir/logs/latest.log"
    touch "$state_file"

    cat > "$api_response" <<JSON
[
  {
    "id": 74,
    "channel": "STABLE",
    "downloads": {
      "server:default": {
        "name": "paper-26.1.2-74.jar",
        "url": "https://fill-data.papermc.io/v1/objects/$new_sha/paper-26.1.2-74.jar",
        "checksums": {"sha256": "$new_sha"},
        "size": $new_size
      }
    }
  },
  {
    "id": 73,
    "channel": "BETA",
    "downloads": {
      "server:default": {
        "name": "paper-26.1.2-73.jar",
        "url": "https://fill-data.papermc.io/v1/objects/$new_sha/paper-26.1.2-73.jar",
        "checksums": {"sha256": "$new_sha"},
        "size": $new_size
      }
    }
  }
]
JSON

    cat > "$scenario/manager.conf" <<CONFIG
MC_DIR="$mc_dir"
TMUX_SESSION="mcserver"
START_COMMAND="./start.sh"
MINECRAFT_PORT="25565"
SERVER_LOG="logs/latest.log"
READY_PATTERN="Done"
START_TIMEOUT_SECONDS="3"
STOP_TIMEOUT_SECONDS="30"
BACKUP_DIR="$backup_dir"
BACKUP_RETENTION="3"
PLAYIT_AUTO_START="false"
PLAYIT_COMMAND="playit"
PLAYIT_SESSION="playit-tunnel"
PLAYIT_STOP_WITH_SERVER="false"
PAPER_JAR="server.jar"
PAPER_PREVIOUS_JAR_RETENTION="3"
CONFIG

    local output rc check_output
    check_output="$(env PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$scenario/manager.conf" MOCK_DOWNLOAD_FILE="$new_jar" MOCK_API_RESPONSE="$api_response" MOCK_MC_DIR="$mc_dir" MOCK_STATE_FILE="$state_file" MOCK_NEW_SHA="$new_sha" MOCK_MC_VERSION=26.1.2 MOCK_OLD_BUILD=61 MOCK_NEW_BUILD=74 MOCK_FAIL_NEW="$fail_new" "$ROOT/hagonoy" paper-check 2>&1)"
    grep -Fq 'Installed Paper build:       61' <<< "$check_output" || {
        printf '[FAIL] %s scenario: installed build was not detected\n%s\n' "$name" "$check_output" >&2
        return 1
    }
    grep -Fq 'Latest stable Paper build:   74' <<< "$check_output" || {
        printf '[FAIL] %s scenario: stable build was not selected\n%s\n' "$name" "$check_output" >&2
        return 1
    }
    printf '[OK] Paper check detects installed build and selects stable build only\n'

    if [[ "$fail_new" == "true" ]]; then
        set +e
        output="$(printf 'y\n' | env PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$scenario/manager.conf" MOCK_DOWNLOAD_FILE="$new_jar" MOCK_API_RESPONSE="$api_response" MOCK_MC_DIR="$mc_dir" MOCK_STATE_FILE="$state_file" MOCK_NEW_SHA="$new_sha" MOCK_MC_VERSION=26.1.2 MOCK_OLD_BUILD=61 MOCK_NEW_BUILD=74 MOCK_FAIL_NEW="$fail_new" "$ROOT/hagonoy" paper-update 2>&1)"
        rc=$?
        set -e
        [[ "$rc" -ne 0 ]] || {
            printf '[FAIL] %s scenario: update should report failure after rollback\n%s\n' "$name" "$output" >&2
            return 1
        }
        [[ "$(sha256sum "$mc_dir/server.jar" | awk '{print $1}')" == "$old_sha" ]] || {
            printf '[FAIL] %s scenario: old JAR hash was not restored\n' "$name" >&2
            return 1
        }
        [[ -f "$state_file" ]] || {
            printf '[FAIL] %s scenario: previous server did not restart\n%s\n' "$name" "$output" >&2
            return 1
        }
        grep -Fq 'Rollback start completed on Paper build 61' <<< "$output" || {
            printf '[FAIL] %s scenario: rollback confirmation missing\n%s\n' "$name" "$output" >&2
            return 1
        }
        printf '[OK] Failed startup restores previous JAR and restarts old build\n'
    else
        output="$(printf 'y\n' | env PATH="$MOCK_BIN:$PATH" HAGONOY_CONFIG="$scenario/manager.conf" MOCK_DOWNLOAD_FILE="$new_jar" MOCK_API_RESPONSE="$api_response" MOCK_MC_DIR="$mc_dir" MOCK_STATE_FILE="$state_file" MOCK_NEW_SHA="$new_sha" MOCK_MC_VERSION=26.1.2 MOCK_OLD_BUILD=61 MOCK_NEW_BUILD=74 MOCK_FAIL_NEW="$fail_new" "$ROOT/hagonoy" paper-update 2>&1)"
        [[ "$(sha256sum "$mc_dir/server.jar" | awk '{print $1}')" == "$new_sha" ]] || {
            printf '[FAIL] %s scenario: new JAR was not installed\n%s\n' "$name" "$output" >&2
            return 1
        }
        [[ -f "$state_file" ]] || {
            printf '[FAIL] %s scenario: updated server did not start\n%s\n' "$name" "$output" >&2
            return 1
        }
        find "$mc_dir" -maxdepth 1 -type f -name 'server.jar.previous-*' | grep -q . || {
            printf '[FAIL] %s scenario: previous JAR was not retained\n' "$name" >&2
            return 1
        }

        for index in 1 2 3 4; do
            jar_fixture="$mc_dir/server.jar.previous-2020010${index}-000000-build$((50 + index))"
            [[ -f "$jar_fixture" ]] || {
                printf '[FAIL] %s scenario: existing previous JAR was deleted: %s\n' "$name" "$jar_fixture" >&2
                return 1
            }
        done
        printf '[OK] Existing previous Paper JARs are preserved; no automatic pruning\n'

        local backup
        backup="$(find "$backup_dir" -maxdepth 1 -type f -name 'hagonoy-smp-*.tar' | head -n 1)"
        [[ -n "$backup" ]] && tar -tf "$backup" >/dev/null || {
            printf '[FAIL] %s scenario: pre-update backup missing or unreadable\n' "$name" >&2
            return 1
        }
        grep -Fq 'Paper update successful: Minecraft 26.1.2, Paper build 74.' <<< "$output" || {
            printf '[FAIL] %s scenario: update success confirmation missing\n%s\n' "$name" "$output" >&2
            return 1
        }
        printf '[OK] Stable Paper update verifies JAR, backs up, preserves old JAR and starts new build\n'
    fi

    for index in 1 2 3 4; do
        backup_fixture="$backup_dir/hagonoy-smp-2020010${index}-000000.tar"
        [[ -f "$backup_fixture" ]] || {
            printf '[FAIL] %s scenario: existing backup archive was deleted: %s\n' "$name" "$backup_fixture" >&2
            return 1
        }
    done
    printf '[OK] Existing backup archives are preserved; no automatic pruning\n'
}

run_scenario "success" "false"
run_scenario "rollback" "true"
