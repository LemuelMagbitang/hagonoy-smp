#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader("hsmp_core_plan", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

runtime = {"pid": "123", "paper_version": "26.3-244-main@test", "minecraft_version": "26.3"}


def plugin_jar(path, name, version, payload=b"old"):
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("plugin.yml", f"name: {name}\nversion: {version}\n")
        archive.writestr("fixture.bin", payload)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def setup(root):
    server = root / "server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.3\n"
        "This server is running Paper version 26.3-244-main@test (test)\n"
    )
    (server / "server.jar").write_bytes(b"paper-current")
    plugins = server / "plugins"
    plugins.mkdir()
    geyser_sha = plugin_jar(plugins / "Geyser-Spigot.jar", "Geyser-Spigot", "2.12.1-SNAPSHOT")
    floodgate_sha = plugin_jar(plugins / "floodgate-spigot.jar", "floodgate", "2.2.5-SNAPSHOT")
    chunky = plugin_jar(plugins / "Chunky-Bukkit-1.5.3.jar", "Chunky", "1.5.3")
    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", runtime["paper_version"], "26.3")
        module.begin(server, "ubuntu", runtime["paper_version"], "26.3")
    return server, geyser_sha, floodgate_sha, chunky

paper_current = {"build": 244, "name": "paper.jar", "url": "https://example.invalid/paper.jar", "sha256": "a" * 64, "size": 123}
geyser_new_sha = "b" * 64
floodgate_current_sha = None

def geyser_metadata(project, current_geyser_sha, current_floodgate_sha):
    if project == "geyser":
        return {"project": "geyser", "version": "2.12.1", "build": 1300,
                "name": "Geyser-Spigot.jar", "sha256": geyser_new_sha,
                "platform": "spigot", "build_history": [
                    {"build": 1295, "downloads": {"spigot": {"sha256": current_geyser_sha}}},
                    {"build": 1300, "downloads": {"spigot": {"sha256": geyser_new_sha}}},
                ]}
    return {"project": "floodgate", "version": "2.2.5", "build": 141,
            "name": "floodgate-spigot.jar", "sha256": current_floodgate_sha,
            "platform": "spigot", "build_history": [
                {"build": 141, "downloads": {"spigot": {"sha256": current_floodgate_sha}}},
            ]}

print("========== PLAN: INSTALLED-ONLY AND NO WRITES ==========")
with tempfile.TemporaryDirectory() as temporary:
    server, geyser_sha, floodgate_sha, chunky_sha = setup(Path(temporary))
    original_server = (server / "server.jar").read_bytes()
    original_geyser = (server / "plugins" / "Geyser-Spigot.jar").read_bytes()
    original_floodgate = (server / "plugins" / "floodgate-spigot.jar").read_bytes()
    original_chunky = (server / "plugins" / "Chunky-Bukkit-1.5.3.jar").read_bytes()
    output = io.StringIO()
    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "fetch_paper_stable_build", return_value=paper_current), \
         patch.object(module, "fetch_geysermc_default_build",
                      side_effect=lambda project, agent: geyser_metadata(project, geyser_sha, floodgate_sha)), \
         patch.object(module, "download_verified_paper_build") as paper_download, \
         patch.object(module, "download_verified_geysermc_artifact") as plugin_download, \
         patch.object(module, "stop_managed_server") as stop, \
         contextlib.redirect_stdout(output):
        module.update_core_server(server, "mcserver", 25565, "Done", 900, 180, "test-agent", "plan")
    result = output.getvalue()
    assert "[UPDATE] Geyser-Spigot" in result
    assert "[CURRENT] floodgate" in result
    assert "[UNCHANGED] All plugins outside" in result
    assert "RESULT=READY_FOR_CORE_UPDATE" in result
    assert stop.call_count == 0 and paper_download.call_count == 0 and plugin_download.call_count == 0
    assert (server / "server.jar").read_bytes() == original_server
    assert (server / "plugins" / "Geyser-Spigot.jar").read_bytes() == original_geyser
    assert (server / "plugins" / "floodgate-spigot.jar").read_bytes() == original_floodgate
    assert (server / "plugins" / "Chunky-Bukkit-1.5.3.jar").read_bytes() == original_chunky
    assert not list(server.rglob(".hagonoy-core-*.part"))
    print("[OK] Plan updates only older installed Geyser, skips current Floodgate, and leaves Paper/server files and Chunky untouched.")

print("========== PLAN: MISSING COMPONENT IS NOT INSTALLED ==========")
with tempfile.TemporaryDirectory() as temporary:
    server = Path(temporary) / "server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.3\n"
        "This server is running Paper version 26.3-244-main@test (test)\n"
    )
    (server / "server.jar").write_bytes(b"paper-current")
    (server / "plugins").mkdir()
    geyser_sha = plugin_jar(server / "plugins" / "Geyser-Spigot.jar", "Geyser-Spigot", "2.12.1-SNAPSHOT")
    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", runtime["paper_version"], "26.3")
        module.begin(server, "ubuntu", runtime["paper_version"], "26.3")
    called = []
    def lookup(project, agent):
        called.append(project)
        return {"project": "geyser", "version": "2.12.1", "build": 1300,
                "name": "Geyser-Spigot.jar", "sha256": "b" * 64,
                "platform": "spigot", "build_history": [
                    {"build": 1295, "downloads": {"spigot": {"sha256": geyser_sha}}}
                ]}
    output = io.StringIO()
    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "fetch_paper_stable_build", return_value=paper_current), \
         patch.object(module, "fetch_geysermc_default_build", side_effect=lookup), \
         contextlib.redirect_stdout(output):
        module.update_core_server(server, "mcserver", 25565, "Done", 900, 180, "test-agent", "plan")
    assert called == ["geyser"], called
    assert "[SKIP_NOT_INSTALLED] Floodgate" in output.getvalue()
    print("[OK] Missing Floodgate is skipped and never queried for installation.")

print("========== PLAN: ALL COMPONENTS CURRENT ==========")
with tempfile.TemporaryDirectory() as temporary:
    server, geyser_sha, floodgate_sha, chunky_sha = setup(Path(temporary))
    current_paper = dict(paper_current, build=244)
    def current_metadata(project, agent):
        if project == "geyser":
            return {"project": "geyser", "version": "2.12.1", "build": 1300,
                    "name": "Geyser-Spigot.jar", "sha256": geyser_sha,
                    "platform": "spigot", "build_history": []}
        return {"project": "floodgate", "version": "2.2.5", "build": 141,
                "name": "floodgate-spigot.jar", "sha256": floodgate_sha,
                "platform": "spigot", "build_history": []}
    output = io.StringIO()
    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "fetch_paper_stable_build", return_value=current_paper), \
         patch.object(module, "fetch_geysermc_default_build", side_effect=current_metadata), \
         patch.object(module, "download_verified_paper_build") as paper_download, \
         patch.object(module, "download_verified_geysermc_artifact") as plugin_download, \
         patch.object(module, "stop_managed_server") as stop, \
         contextlib.redirect_stdout(output):
        module.update_core_server(server, "mcserver", 25565, "Done", 900, 180, "test-agent", "execute")
    assert "CORE_UPDATE=ALREADY_CURRENT" in output.getvalue()
    assert "No download, shutdown, JAR replacement, or restart was performed." in output.getvalue()
    assert stop.call_count == 0 and paper_download.call_count == 0 and plugin_download.call_count == 0
    print("[OK] When Paper, Geyser, and Floodgate already match official current artifacts, execute exits without stopping or writing anything.")

print("========== INSTALLED PLUGIN IDENTITY FAIL-CLOSED ==========")
with tempfile.TemporaryDirectory() as temporary:
    server = Path(temporary) / "server"
    plugins = server / "plugins"
    plugins.mkdir(parents=True)
    plugin_jar(plugins / "GeyserBridge.jar", "GeyserBridge", "1.0.0")
    try:
        module.inspect_installed_managed_plugins(server)
    except RuntimeError as exc:
        assert "unrecognized descriptor identity" in str(exc)
    else:
        raise AssertionError("An unrelated Geyser-named plugin was treated as Geyser-Spigot.")
    print("[OK] A JAR merely containing 'Geyser' in its name is not mistaken for the managed Geyser-Spigot plugin.")

print("[DONE] Core updater plan tests passed.")
PY
