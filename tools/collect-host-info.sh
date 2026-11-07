#!/usr/bin/env bash
# Read-only, privacy-conscious diagnostics for the Hagonoy SMP Ubuntu host.
# Does not start/stop Minecraft, change files, or print credentials/process arguments.
set -Eeuo pipefail

section() { printf '\n===== %s =====\n' "$1"; }

if (( $# > 1 )); then
    printf 'Usage: %s [minecraft-server-directory]\n' "$0" >&2
    exit 2
fi

section 'Operating system'
if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    printf '%s\n' "${PRETTY_NAME:-Unknown Linux distribution}"
fi
printf 'Kernel: %s\nArchitecture: %s\n' "$(uname -r)" "$(uname -m)"

section 'CPU'
if command -v lscpu >/dev/null 2>&1; then
    lscpu | awk -F: '/^(Model name|CPU\(s\)|Architecture):/ {gsub(/^[ \t]+/, "", $2); print $1 ": " $2}'
elif [[ -r /proc/cpuinfo ]]; then
    awk -F: '/^model name[ \t]*:/ {gsub(/^[ \t]+/, "", $2); print "Model: " $2; exit}' /proc/cpuinfo
fi

section 'Memory and swap'
if command -v free >/dev/null 2>&1; then free -h; else printf 'free command not found\n'; fi
if command -v swapon >/dev/null 2>&1; then
    swapon --show --output=NAME,SIZE,USED,PRIO 2>/dev/null || true
fi

section 'Home filesystem'
df -hT "$HOME"

section 'Available block devices and mount points'
if command -v lsblk >/dev/null 2>&1; then
    lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS 2>/dev/null || true
else
    printf 'lsblk command not found\n'
fi

section 'Tool availability'
for cmd in git tmux rsync tar ss java playit; do
    if command -v "$cmd" >/dev/null 2>&1; then
        printf '[found] %-8s %s\n' "$cmd" "$(command -v "$cmd")"
    else
        printf '[missing] %s\n' "$cmd"
    fi
done
if command -v java >/dev/null 2>&1; then
    java -version 2>&1 | sed -n '1p'
fi
if command -v tmux >/dev/null 2>&1; then
    printf '\nCurrent tmux session names (if any):\n'
    tmux list-sessions -F '  #{session_name}' 2>/dev/null || printf '  no tmux sessions found\n'
fi

CANDIDATE="${1:-$HOME/minecraft-server}"
section 'Minecraft server directory check'
printf 'Candidate path: %s\n' "$CANDIDATE"
if [[ -d "$CANDIDATE" ]]; then
    printf '[found] %s\n' "$CANDIDATE"
    du -sh -- "$CANDIDATE"
    df -hT -- "$CANDIDATE"
    printf 'Recognizable top-level server files:\n'
    find "$CANDIDATE" -maxdepth 2 -type f \
        \( -name 'start.sh' -o -name 'server.properties' -o -name 'paper*.jar' \
        -o -name 'purpur*.jar' -o -name 'fabric-server-launch.jar' \
        -o -name 'forge*.jar' -o -name 'server.jar' \) \
        -printf '  %P\n' | sort | sed -n '1,60p'
else
    printf '[not found] %s\n' "$CANDIDATE"
    printf 'No server files were changed. We need to locate the existing server folder before configuring the manager.\n'
fi

section 'Minecraft port check'
if command -v ss >/dev/null 2>&1; then
    if ss -ltnH 'sport = :25565' 2>/dev/null | grep -q .; then
        printf 'TCP port 25565 is listening.\n'
    else
        printf 'TCP port 25565 is not listening.\n'
    fi
else
    printf 'ss command not found; port check skipped.\n'
fi

printf '\nDiagnostics complete. This script is read-only and does not print process arguments, IP addresses, passwords, or tokens.\n'
