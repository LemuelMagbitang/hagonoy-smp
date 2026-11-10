#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

helper = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("hagonoy_generation_runtime", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    server = root / "server"
    log = server / "logs" / "latest.log"
    proc_root = root / "proc"
    fake_java = root / "bin" / "java"

    log.parent.mkdir(parents=True)
    fake_java.parent.mkdir(parents=True)
    fake_java.write_text("test executable marker")

    log.write_text(
        "[Server thread/INFO]: Starting minecraft server version 26.1.2\n"
        "[Server thread/INFO]: This server is running Paper version "
        "26.1.2-61-main@8dea6f1 (test)\n"
    )

    pid = "4242"
    process = proc_root / pid
    process.mkdir(parents=True)
    (process / "cwd").symlink_to(server)
    (process / "exe").symlink_to(fake_java)

    def good_command(command, **kwargs):
        if command[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(command, 0, str(server) + "\n", "")
        if command[0] == "ss":
            output = (
                'LISTEN 0 4096 *:25565 *:* '
                'users:(("java",pid=4242,fd=99))\n'
            )
            return subprocess.CompletedProcess(command, 0, output, "")
        raise AssertionError(f"Unexpected command: {command}")

    print("========== 1. VALID RUNNING SERVER ==========")
    with patch.object(module.subprocess, "run", side_effect=good_command):
        result = module.verify_running_server(
            server, "ubuntu", "AUTO", "AUTO", "mcserver", 25565,
            proc_root=proc_root
        )

    assert result["pid"] == pid
    assert result["paper_version"] == "26.1.2-61-main@8dea6f1"
    assert result["minecraft_version"] == "26.1.2"
    print("[OK] Running server validated.")

    print()
    print("========== 2. MISSING TMUX SESSION ==========")
    def no_session(command, **kwargs):
        if command[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(command, 1, "", "no server session")
        return good_command(command, **kwargs)

    with patch.object(module.subprocess, "run", side_effect=no_session):
        try:
            module.verify_running_server(
                server, "ubuntu", "AUTO", "AUTO", "mcserver", 25565,
                proc_root=proc_root
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Missing tmux session was accepted.")

    print("[OK] Missing tmux session rejected.")

    print()
    print("========== 3. WRONG PAPER VERSION ==========")
    with patch.object(module.subprocess, "run", side_effect=good_command):
        try:
            module.verify_running_server(
                server, "ubuntu", "wrong-paper", "AUTO", "mcserver", 25565,
                proc_root=proc_root
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Wrong Paper version was accepted.")

    print("[OK] Paper version mismatch rejected.")

    print()
    print("========== 4. EXISTING MANIFEST ==========")
    (server / module.FILENAME).write_text("{}")

    with patch.object(module.subprocess, "run", side_effect=good_command):
        try:
            module.verify_running_server(
                server, "ubuntu", "AUTO", "AUTO", "mcserver", 25565,
                proc_root=proc_root
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Existing manifest was accepted.")

    print("[OK] Existing manifest rejected before runtime checks.")

print()
print("========== ALL RUNTIME TESTS PASSED ==========")
PY
