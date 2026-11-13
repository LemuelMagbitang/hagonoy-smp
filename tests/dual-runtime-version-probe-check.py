#!/usr/bin/env python3
"""Regression tests for live Paper/Minecraft version discovery."""
import importlib.machinery
import importlib.util
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

script = Path(__file__).resolve().parents[1] / "bin" / "hagonoy-generation"
loader = importlib.machinery.SourceFileLoader("hsmp_version_probe", str(script))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)


def check(paper_version, api_version, expected_minecraft):
    baseline = "[Server thread/INFO]: Server console ready\n"
    response = (
        "[Server thread/INFO]: Checking version, please wait...\n"
        f"[Server thread/INFO]: This server is running Paper version {paper_version} "
        f"(2026-11-11T22:00:00Z) (Implementing API version {api_version})\n"
    )
    captures = iter((baseline, response))
    observed_commands = []

    def fake_run_command(command):
        observed_commands.append(list(command))
        if command[:2] == ["tmux", "capture-pane"]:
            return next(captures)
        if command[:2] == ["tmux", "send-keys"]:
            return ""
        raise AssertionError(f"Unexpected command: {command!r}")

    with patch.object(module, "run_command", side_effect=fake_run_command):
        actual_paper, actual_minecraft = module.query_runtime_versions_from_console("mcserver")

    assert actual_paper == paper_version, (actual_paper, paper_version)
    assert actual_minecraft == expected_minecraft, (actual_minecraft, expected_minecraft)
    capture_commands = [item for item in observed_commands if item[:2] == ["tmux", "capture-pane"]]
    assert capture_commands and all("-J" in item for item in capture_commands), capture_commands
    assert any(item[:2] == ["tmux", "send-keys"] and "version" in item for item in observed_commands)


print("========== PAPER 26.3 API VERSION FORMAT ==========")
check(
    "26.3-244-main@35a2d15",
    "26.3.build.244-stable",
    "26.3",
)
print("[OK] Paper 26.3 build-style API version is accepted; Minecraft version is derived from Paper's own build prefix.")

print("========== LEGACY PAPER API VERSION FORMAT ==========")
check(
    "1.21.11-72-main@cd445fd",
    "1.21.11-R0.1-SNAPSHOT",
    "1.21.11",
)
print("[OK] Legacy 1.x Paper API version format remains supported.")

print("========== PAPER BANNER WITHOUT MINECRAFT STARTUP LINE ==========")
assert module.minecraft_version_from_paper_version("26.3-244-main@35a2d15") == "26.3"
assert module.minecraft_version_from_paper_version("1.21.11-72-main@cd445fd") == "1.21.11"
assert module.minecraft_version_from_paper_version("1.21.4-R0.1-SNAPSHOT") == "1.21.4"
assert module.minecraft_version_from_paper_version("git-Paper-217") is None

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    server = root / "server"
    log = server / "logs" / "latest.log"
    proc_root = root / "proc"
    fake_java = root / "bin" / "java"
    log.parent.mkdir(parents=True)
    fake_java.parent.mkdir(parents=True)
    fake_java.write_text("test executable marker", encoding="utf-8")

    # Modern Paper may log its build banner without a separate Minecraft
    # startup-version line. The Paper prefix is sufficient to identify MC.
    log.write_text(
        "[Server thread/INFO]: This server is running Paper version "
        "26.3-244-main@35a2d15 (2026-11-06T11:34:02Z) "
        "(Implementing API version 26.3.build.244-stable)\n",
        encoding="utf-8",
    )

    process = proc_root / "4242"
    process.mkdir(parents=True)
    (process / "cwd").symlink_to(server)
    (process / "exe").symlink_to(fake_java)

    def fake_run_command(command, **kwargs):
        if command[:2] == ["tmux", "has-session"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["tmux", "list-panes"]:
            return subprocess.CompletedProcess(command, 0, f"{server}\n", "")
        if command[0] == "ss" and "-ltnp" in command:
            output = 'LISTEN 0 4096 *:25565 *:* users:(("java",pid=4242,fd=99))\n'
            return subprocess.CompletedProcess(command, 0, output, "")
        if command[0] == "ss" and "-lunp" in command:
            output = 'UNCONN 0 0 *:19132 *:* users:(("java",pid=4242,fd=100))\n'
            return subprocess.CompletedProcess(command, 0, output, "")
        raise AssertionError(f"Unexpected runtime verification command: {command!r}")

    with patch.object(module.subprocess, "run", side_effect=fake_run_command):
        with patch.object(
            module,
            "query_runtime_versions_from_console",
            side_effect=AssertionError("Console query should not be needed when Paper's build banner is present."),
        ):
            observed = module.verify_running_server(
                server,
                "ubuntu",
                "AUTO",
                "AUTO",
                "mcserver",
                25565,
                proc_root=proc_root,
            )

    assert observed["paper_version"] == "26.3-244-main@35a2d15"
    assert observed["minecraft_version"] == "26.3"
print("[OK] Runtime verification derives Minecraft 26.3 from the Paper banner without querying the console.")

print("[DONE] Live runtime version probe regression tests passed.")
