#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "${EUID}" -eq 0 ]]; then
    SUDO=""
elif command -v sudo >/dev/null 2>&1; then
    SUDO="sudo"
else
    echo "ERROR: sudo is required to install system packages." >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer currently supports Ubuntu/Debian systems using apt-get." >&2
    exit 1
fi

$SUDO apt-get update
$SUDO apt-get install -y git tmux rsync tar coreutils iproute2

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
chmod +x "$ROOT/hagonoy" "$ROOT/bin/hagonoy"

if [[ ! -f "$ROOT/config/manager.conf" ]]; then
    cp "$ROOT/config/manager.conf.example" "$ROOT/config/manager.conf"
    echo "Created config/manager.conf from the example. Edit MC_DIR and other settings before use."
else
    echo "Keeping existing config/manager.conf."
fi

echo "Installation dependencies are ready. Next: edit config/manager.conf, then run ./hagonoy doctor."
echo "Java and Playit are intentionally not installed automatically; their required versions/settings depend on your server."
