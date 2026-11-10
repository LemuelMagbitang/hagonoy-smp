#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import contextlib
import importlib.machinery
import importlib.util
import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

helper = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("hagonoy_generation_lifecycle", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

runtime = {
    "pid": "71212",
    "paper_version": "26.1.2-61-main@8dea6f1",
    "minecraft_version": "26.1.2"
}

def make_server(root, state="stopped"):
    server = root / "server"
    (server / "logs").mkdir(parents=True)
    (server / "start.sh").write_text("#!/bin/bash\nexec java -jar server.jar nogui\n")
    (server / "start.sh").chmod(0o755)
    (server / "server.jar").write_bytes(b"test fixture only")
    (server / "logs" / "latest.log").write_text("old log content\n")

    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", runtime["paper_version"], runtime["minecraft_version"])
        if state == "running":
            module.begin(server, "ubuntu", runtime["paper_version"], runtime["minecraft_version"])

    return server

def completed(code=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], code, stdout, stderr)

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)

    print("========== 0. EXACT TMUX PANE TARGET ==========")

    with patch.object(module, "run_command", return_value="mcserver:0.0\n"):
        assert module.get_tmux_pane_target("mcserver") == "mcserver:0.0"

    invalid_pane_results = [
        "",
        "mcserver:0.0\nmcserver:0.1\n",
        "other:0.0\n",
        "mcserver:x.0\n",
    ]

    for pane_result in invalid_pane_results:
        with patch.object(module, "run_command", return_value=pane_result):
            try:
                module.get_tmux_pane_target("mcserver")
            except RuntimeError:
                pass
            else:
                raise AssertionError(
                    f"Unsafe tmux pane result was accepted: {pane_result!r}"
                )

    print("[OK] Exact pane accepted; missing, ambiguous, and malformed panes rejected.")

    print("========== 1. STOPPED SERVER VERIFICATION ==========")
    server = make_server(root / "verify")

    with patch.object(module, "probe_command", return_value=completed(1)), \
         patch.object(module, "run_command", return_value=""):
        data = module.verify_stopped_server(server, "mcserver", 25565)
        assert data["state"] == "stopped"

    with patch.object(module, "probe_command", return_value=completed(0)), \
         patch.object(module, "run_command", return_value=""):
        try:
            module.verify_stopped_server(server, "mcserver", 25565)
        except RuntimeError:
            pass
        else:
            raise AssertionError("A running tmux session was accepted as stopped.")

    with patch.object(module, "probe_command", return_value=completed(1)), \
         patch.object(module, "run_command", return_value="LISTEN 0 10 *:25565 *:*"):
        try:
            module.verify_stopped_server(server, "mcserver", 25565)
        except RuntimeError:
            pass
        else:
            raise AssertionError("An active TCP listener was accepted as stopped.")

    print("[OK] Stopped state requires absent tmux session and closed port.")

    print()
    print("========== 2. SUCCESSFUL START ADVANCES ONCE ==========")
    server = make_server(root / "start-success")
    log_path = server / "logs" / "latest.log"

    def launch_and_log(command):
        if command[:2] == ["tmux", "new-session"]:
            with log_path.open("a") as stream:
                stream.write("Done (test server ready)!\n")
        return ""

    with patch.object(module, "verify_stopped_server", return_value=module.load(server)), \
         patch.object(module, "run_command", side_effect=launch_and_log), \
         patch.object(module, "probe_command", return_value=completed(0)), \
         patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module.time, "sleep", return_value=None), \
         contextlib.redirect_stdout(io.StringIO()):
        module.start_managed_server(server, "mcserver", 25565, "Done", 5)

    data = module.load(server)
    assert data["generation"] == 2
    assert data["state"] == "running"
    assert data["paper_version"] == runtime["paper_version"]
    assert data["minecraft_version"] == runtime["minecraft_version"]
    first_running_id = data["generation_id"]
    print("[OK] Start creates generation 2 and records verified versions.")

    print()
    print("========== 2B. TRANSIENT RUNTIME VERIFICATION ==========")
    delayed_server = make_server(root / "start-delayed-verification")
    log_path = delayed_server / "logs" / "latest.log"
    verification_attempts = []

    def delayed_verification(*args, **kwargs):
        verification_attempts.append(True)
        if len(verification_attempts) == 1:
            raise RuntimeError(
                "Windows Java server or Bedrock listener could not be verified."
            )
        return runtime

    with patch.object(module, "verify_stopped_server", return_value=module.load(delayed_server)), \
         patch.object(module, "run_command", side_effect=launch_and_log), \
         patch.object(module, "probe_command", return_value=completed(0)), \
         patch.object(module, "verify_running_server", side_effect=delayed_verification), \
         patch.object(module.time, "monotonic", side_effect=[0.0, 2.0]), \
         patch.object(module.time, "sleep", return_value=None), \
         contextlib.redirect_stdout(io.StringIO()):
        module.start_managed_server(delayed_server, "mcserver", 25565, "Done", 5)

    data = module.load(server)
    assert len(verification_attempts) == 2
    assert data["generation"] == 2
    assert data["state"] == "running"
    assert data["paper_version"] == runtime["paper_version"]
    assert data["minecraft_version"] == runtime["minecraft_version"]
    print("[OK] Transient runtime verification failure retries and succeeds.")

    print()
    print("========== 3. START IS IDEMPOTENT ==========")
    with patch.object(module, "verify_running_server", return_value=runtime), \
         contextlib.redirect_stdout(io.StringIO()):
        module.start_managed_server(server, "mcserver", 25565, "Done", 5)

    data = module.load(server)
    assert data["generation"] == 2
    assert data["generation_id"] == first_running_id
    print("[OK] Already-running server does not advance generation.")

    print()
    print("========== 4. FAILED START REMAINS UNCERTAIN ==========")
    server = make_server(root / "start-failure")

    clock = iter([0.0, 0.0, 2.0])
    with patch.object(module, "verify_stopped_server", return_value=module.load(server)), \
         patch.object(module, "run_command", return_value=""), \
         patch.object(module, "probe_command", return_value=completed(0)), \
         patch.object(module.time, "monotonic", side_effect=lambda: next(clock)), \
         patch.object(module.time, "sleep", return_value=None), \
         contextlib.redirect_stdout(io.StringIO()):
        try:
            module.start_managed_server(server, "mcserver", 25565, "NEVER-SEEN", 1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Startup timeout unexpectedly succeeded.")

    data = module.load(server)
    assert data["generation"] == 2
    assert data["state"] == "running"
    print("[OK] Failed startup leaves generation RUNNING; no false stopped state.")

    print()
    print("========== 5. SUCCESSFUL GRACEFUL STOP ==========")
    server = make_server(root / "stop-success", state="running")
    commands = []

    def record_stop(command):
        commands.append(command)
        if command[:3] == ["tmux", "send-keys", "-t"]:
            assert len(command) > 3, command
            assert command[3] == "mcserver:0.0", command
        return ""

    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "get_tmux_pane_target", return_value="mcserver:0.0"), \
         patch.object(module, "run_command", side_effect=record_stop), \
         patch.object(module, "probe_command", return_value=completed(1)), \
         patch.object(module.time, "sleep", return_value=None), \
         contextlib.redirect_stdout(io.StringIO()):
        module.stop_managed_server(server, "mcserver", 25565, 5)

    data = module.load(server)
    assert data["state"] == "stopped"
    assert any("save-all flush" in command for command in commands)
    assert any("stop" in command for command in commands)
    assert not any("kill" in " ".join(command) for command in commands)
    print("[OK] Graceful save and stop marks generation STOPPED.")

    print()
    print("========== 6. FAILED STOP REMAINS RUNNING ==========")
    server = make_server(root / "stop-failure", state="running")
    clock = iter([0.0, 0.0, 2.0])
    commands = []

    def persistent_listener(command):
        commands.append(command)
        if command[0] == "ss":
            return "LISTEN 0 10 *:25565 *:*"
        return ""

    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "get_tmux_pane_target", return_value="mcserver:0.0"), \
         patch.object(module, "run_command", side_effect=persistent_listener), \
         patch.object(module, "probe_command", return_value=completed(0)), \
         patch.object(module.time, "monotonic", side_effect=lambda: next(clock)), \
         patch.object(module.time, "sleep", return_value=None), \
         contextlib.redirect_stdout(io.StringIO()):
        try:
            module.stop_managed_server(server, "mcserver", 25565, 1)
        except RuntimeError:
            pass
        else:
            raise AssertionError("Shutdown timeout unexpectedly succeeded.")

    data = module.load(server)
    assert data["state"] == "running"
    assert not any("kill" in " ".join(command) for command in commands)
    print("[OK] Failed shutdown leaves generation RUNNING and never force-kills.")

print()
print("========== ALL LIFECYCLE TESTS PASSED ==========")
PY
