#!/usr/bin/env python3
"""Regression tests for live Paper/Minecraft version discovery."""
import importlib.machinery
import importlib.util
import sys
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

print("[DONE] Live runtime version probe regression tests passed.")
