#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import contextlib
import hashlib
import os
import stat
import importlib.machinery
import importlib.util
import io
import sys
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader("hsmp_core_execution", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

old_paper = b"old Paper binary fixture"
new_paper = b"new Paper binary fixture"
old_geyser = None
new_geyser = None
old_floodgate = None
new_floodgate = None


def make_plugin_bytes(name, version, payload):
    import io as _io
    buffer = _io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("plugin.yml", f"name: {name}\nversion: {version}\n")
        archive.writestr("fixture.bin", payload)
    return buffer.getvalue()

old_geyser = make_plugin_bytes("Geyser-Spigot", "2.12.1-SNAPSHOT", b"geyser-old")
new_geyser = make_plugin_bytes("Geyser-Spigot", "2.12.1-SNAPSHOT", b"geyser-new")
old_floodgate = make_plugin_bytes("floodgate", "2.2.4-SNAPSHOT", b"floodgate-old")
new_floodgate = make_plugin_bytes("floodgate", "2.2.5-SNAPSHOT", b"floodgate-new")
old_hash = lambda value: hashlib.sha256(value).hexdigest()

paper_meta = {
    "build": 245, "name": "paper-26.3-245.jar",
    "url": "https://example.invalid/paper.jar",
    "sha256": old_hash(new_paper), "size": len(new_paper),
}
plugin_meta = {
    "geyser": {
        "project": "geyser", "version": "2.12.1", "build": 1300,
        "channel": "default", "name": "Geyser-Spigot.jar",
        "url": "https://example.invalid/geyser.jar", "sha256": old_hash(new_geyser),
        "platform": "spigot", "build_history": [
            {"build": 1295, "downloads": {"spigot": {"sha256": old_hash(old_geyser)}}},
        ],
    },
    "floodgate": {
        "project": "floodgate", "version": "2.2.5", "build": 142,
        "channel": "default", "name": "floodgate-spigot.jar",
        "url": "https://example.invalid/floodgate.jar", "sha256": old_hash(new_floodgate),
        "platform": "spigot", "build_history": [
            {"build": 141, "downloads": {"spigot": {"sha256": old_hash(old_floodgate)}}},
        ],
    },
}

old_runtime = {
    "pid": "111", "paper_version": "26.3-244-main@old", "minecraft_version": "26.3"
}
new_runtime = {
    "pid": "222", "paper_version": "26.3-245-main@new", "minecraft_version": "26.3"
}


def write_plugin(path, contents):
    path.write_bytes(contents)


def setup(root):
    server = root / "minecraft-server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.3\n"
        "This server is running Paper version 26.3-244-main@old (test)\n",
        encoding="utf-8",
    )
    (server / "server.jar").write_bytes(old_paper)
    plugins = server / "plugins"
    plugins.mkdir()
    write_plugin(plugins / "Geyser-Spigot.jar", old_geyser)
    write_plugin(plugins / "floodgate-spigot.jar", old_floodgate)
    chunky = make_plugin_bytes("Chunky", "1.5.3", b"chunky-unchanged")
    write_plugin(plugins / "Chunky-Bukkit-1.5.3.jar", chunky)
    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", old_runtime["paper_version"], "26.3")
        module.begin(server, "ubuntu", old_runtime["paper_version"], "26.3")
    return server, chunky


def set_state(server, state, paper_version):
    data = module.load(server)
    data["state"] = state
    data["paper_version"] = paper_version
    data["minecraft_version"] = "26.3"
    stamp = module.now()
    data["updated_at_utc"] = stamp
    if state == "stopped":
        data["stopped_at_utc"] = stamp
    else:
        data["started_at_utc"] = stamp
        data["stopped_at_utc"] = None
    module.save(server, data)


def run_transaction(name, fail_runtime_check):
    with tempfile.TemporaryDirectory(prefix=f"hsmp-core-{name}-") as temporary:
        server, chunky_bytes = setup(Path(temporary))
        jar_targets = {
            "paper": server / "server.jar",
            "geyser": server / "plugins" / "Geyser-Spigot.jar",
            "floodgate": server / "plugins" / "floodgate-spigot.jar",
        }
        original_bytes = {key: path.read_bytes() for key, path in jar_targets.items()}
        original_modes = {key: stat.S_IMODE(path.stat().st_mode) for key, path in jar_targets.items()}
        original_world = server / "world"
        original_world.mkdir()
        (original_world / "marker.dat").write_bytes(b"world-not-touched")
        (server / "server.properties").write_text("motd=unchanged\n")
        original_properties = (server / "server.properties").read_bytes()
        original_chunky = (server / "plugins" / "Chunky-Bukkit-1.5.3.jar").read_bytes()

        def fake_paper_download(_metadata, destination, _agent):
            Path(destination).write_bytes(new_paper)

        def fake_plugin_download(metadata, destination, _agent):
            payload = new_geyser if metadata["project"] == "geyser" else new_floodgate
            Path(destination).write_bytes(payload)

        def fake_stop(directory, _session, _port, _timeout, **_kwargs):
            current_paper = old_runtime["paper_version"] if (directory / "server.jar").read_bytes() == old_paper else new_runtime["paper_version"]
            set_state(directory, "stopped", current_paper)

        def fake_start(directory, _session, _port, _ready, _timeout, **_kwargs):
            paper_is_new = (directory / "server.jar").read_bytes() == new_paper
            if paper_is_new:
                set_state(directory, "stopped", new_runtime["paper_version"])
                module.begin(directory, "ubuntu", new_runtime["paper_version"], "26.3")
            else:
                set_state(directory, "stopped", old_runtime["paper_version"])
                module.begin(directory, "ubuntu", old_runtime["paper_version"], "26.3")

        runtime_sequence = [old_runtime]
        if fail_runtime_check:
            runtime_sequence.extend([new_runtime, new_runtime, old_runtime])
        else:
            runtime_sequence.append(new_runtime)

        def runtime_probe(*_args, **_kwargs):
            if not runtime_sequence:
                return new_runtime if not fail_runtime_check else old_runtime
            return runtime_sequence.pop(0)

        def plugin_probe(_session, _plugin_name, expected_version, timeout=12):
            if fail_runtime_check and plugin_probe.calls == 0:
                plugin_probe.calls += 1
                raise RuntimeError("mock Geyser runtime version mismatch")
            plugin_probe.calls += 1
            return expected_version
        plugin_probe.calls = 0

        output = io.StringIO()
        error = None
        with patch.object(module, "verify_running_server", side_effect=runtime_probe), \
             patch.object(module, "fetch_paper_stable_build", return_value=paper_meta), \
             patch.object(module, "fetch_geysermc_default_build", side_effect=lambda project, agent: plugin_meta[project]), \
             patch.object(module, "fetch_geysermc_default_builds", side_effect=lambda project, version, agent: [
                 {"build": 140, "channel": "default", "downloads": {"spigot": {"sha256": old_hash(old_floodgate)}}}
             ] if project == "floodgate" and version == "2.2.4" else []), \
             patch.object(module, "download_verified_paper_build", side_effect=fake_paper_download), \
             patch.object(module, "download_verified_geysermc_artifact", side_effect=fake_plugin_download), \
             patch.object(module, "stop_managed_server", side_effect=fake_stop) as stop, \
             patch.object(module, "start_managed_server", side_effect=fake_start) as start, \
             patch.object(module, "query_plugin_version_from_console", side_effect=plugin_probe), \
             patch.object(module, "probe_command", return_value=SimpleNamespace(returncode=0, stderr="")), \
             contextlib.redirect_stdout(output):
            try:
                module.update_core_server(
                    server, "mcserver", 25565, "Done", 900, 180,
                    "test-agent (https://example.invalid)", "execute"
                )
            except RuntimeError as exc:
                error = exc

        result = output.getvalue()
        if fail_runtime_check:
            assert error is not None, "runtime failure should be reported after rollback"
            assert "restored" in str(error).lower() and "restarted successfully" in str(error).lower(), str(error)
            assert {key: path.read_bytes() for key, path in jar_targets.items()} == original_bytes
            assert {key: stat.S_IMODE(path.stat().st_mode) for key, path in jar_targets.items()} == original_modes
            assert start.call_count == 2, start.call_count
            assert stop.call_count == 2, stop.call_count
            print("[OK] Failed plugin runtime verification restores Paper, Geyser, and Floodgate together, then restarts the original set.")
        else:
            assert error is None, f"successful update raised: {error}"
            assert (server / "server.jar").read_bytes() == new_paper
            assert (server / "plugins" / "Geyser-Spigot.jar").read_bytes() == new_geyser
            assert (server / "plugins" / "floodgate-spigot.jar").read_bytes() == new_floodgate
            assert stat.S_IMODE((server / "plugins" / "Geyser-Spigot.jar").stat().st_mode) == original_modes["geyser"]
            assert stat.S_IMODE((server / "plugins" / "floodgate-spigot.jar").stat().st_mode) == original_modes["floodgate"]
            assert "CORE_UPDATE=SUCCESS" in result
            assert start.call_count == 1 and stop.call_count == 1
            print("[OK] Paper, Geyser, and Floodgate are staged and replaced together; runtime checks pass.")

        assert module.load(server)["state"] == "running"
        assert (server / "plugins" / "Chunky-Bukkit-1.5.3.jar").read_bytes() == original_chunky
        assert (server / "server.properties").read_bytes() == original_properties
        assert (original_world / "marker.dat").read_bytes() == b"world-not-touched"
        assert not list(server.rglob(".hagonoy-core-*.part")), "staged JAR leaked"
        assert not list(server.rglob(".hagonoy-core-restore-*.part")), "restore staging JAR leaked"
        assert not list(server.parent.glob(".hagonoy-core-update-transaction-*")), "transaction directory leaked"
        print("[OK] Unrelated plugin, world, config, and temporary-file cleanup invariants hold.")


print("========== HSMP CORE UPDATE TRANSACTION TESTS ==========")
run_transaction("success", False)
run_transaction("rollback", True)
print("[DONE] Core update execution tests passed.")
PY
