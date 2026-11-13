#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

helper = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("hagonoy_generation_paper_execution", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

old_bytes = b"old paper jar fixture"
new_bytes = b"new paper jar fixture"
old_version = "26.1.2-61-main@8dea6f1"
new_version = "26.1.2-62-main@mock"
runtime = {"pid": "71212", "paper_version": old_version, "minecraft_version": "26.1.2"}
metadata = {
    "build": 62,
    "name": "paper-26.1.2-62.jar",
    "url": "https://example.invalid/paper.jar",
    "sha256": hashlib.sha256(new_bytes).hexdigest(),
    "size": len(new_bytes),
}


def setup(root):
    server = root / "minecraft-server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.1.2\n"
        f"This server is running Paper version {old_version} (test)\n",
        encoding="utf-8",
    )
    jar = server / "server.jar"
    jar.write_bytes(old_bytes)
    (server / "server.properties").write_text("motd=keep-this\n", encoding="utf-8")
    (server / "plugins").mkdir()
    (server / "plugins" / "keep.jar").write_bytes(b"plugin bytes stay unchanged")
    (server / "world").mkdir()
    (server / "world" / "marker.dat").write_bytes(b"world bytes stay unchanged")
    (server / "server.jar.rollback-existing").write_bytes(b"pre-existing rollback file")
    (server / "server.jar.failed-existing").write_bytes(b"pre-existing failed file")
    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", old_version, "26.1.2")
        module.begin(server, "ubuntu", old_version, "26.1.2")
    return server, jar


def set_generation(server, state, paper_version):
    data = module.load(server)
    stamp = module.now()
    data["state"] = state
    data["paper_version"] = paper_version
    data["updated_at_utc"] = stamp
    if state == "running":
        data["started_at_utc"] = stamp
        data["stopped_at_utc"] = None
    else:
        data["stopped_at_utc"] = stamp
    module.save(server, data)


def run_case(name, fail_new):
    with tempfile.TemporaryDirectory(prefix=f"hsmp-{name}-") as temporary:
        root = Path(temporary)
        server, jar = setup(root)
        original_properties = (server / "server.properties").read_bytes()
        original_plugin = (server / "plugins" / "keep.jar").read_bytes()
        original_world = (server / "world" / "marker.dat").read_bytes()
        rollback_fixture = (server / "server.jar.rollback-existing").read_bytes()
        failed_fixture = (server / "server.jar.failed-existing").read_bytes()

        def fake_download(_metadata, destination, _user_agent):
            destination.write_bytes(new_bytes)

        def fake_stop(directory, _session, _port, _timeout):
            set_generation(directory, "stopped", old_version)

        start_calls = []

        def fake_start(directory, _session, _port, _ready, _timeout):
            current = (directory / "server.jar").read_bytes()
            if current == new_bytes:
                set_generation(directory, "running", new_version)
                start_calls.append("new")
                if fail_new:
                    raise RuntimeError("mock updated-build readiness failure")
            else:
                set_generation(directory, "running", old_version)
                start_calls.append("old")

        def fake_mark_stopped(directory, _session, _port, _generation_id):
            set_generation(directory, "stopped", new_version)

        output = io.StringIO()
        error = None
        with patch.object(module, "verify_running_server", return_value=runtime), \
             patch.object(module, "fetch_paper_stable_build", return_value=metadata), \
             patch.object(module, "download_verified_paper_build", side_effect=fake_download), \
             patch.object(module, "stop_managed_server", side_effect=fake_stop) as stop, \
             patch.object(module, "start_managed_server", side_effect=fake_start), \
             patch.object(module, "mark_failed_start_stopped", side_effect=fake_mark_stopped), \
             contextlib.redirect_stdout(output):
            try:
                module.update_paper_server(
                    server, "mcserver", 25565, "Done",
                    900, 180, "test-agent (https://example.invalid)",
                    "execute"
                )
            except RuntimeError as exc:
                error = exc

        if fail_new:
            assert error is not None, "failed updated build should report rollback"
            assert "restored" in str(error).lower() and "restarted successfully" in str(error).lower(), str(error)
            assert jar.read_bytes() == old_bytes, "old Paper JAR was not restored"
            assert start_calls == ["new", "old"], start_calls
            print("[OK] Failed update restores and restarts the previous Paper JAR.")
        else:
            assert error is None, f"successful update raised: {error}"
            assert jar.read_bytes() == new_bytes, "new Paper JAR was not installed"
            assert start_calls == ["new"], start_calls
            assert "PAPER_UPDATE=SUCCESS" in output.getvalue()
            print("[OK] Successful update installs the stable JAR.")

        assert stop.call_count == 1
        assert module.load(server)["state"] == "running"
        assert (server / "server.properties").read_bytes() == original_properties
        assert (server / "plugins" / "keep.jar").read_bytes() == original_plugin
        assert (server / "world" / "marker.dat").read_bytes() == original_world
        assert (server / "server.jar.rollback-existing").read_bytes() == rollback_fixture
        assert (server / "server.jar.failed-existing").read_bytes() == failed_fixture
        assert not list(server.glob(".hagonoy-paper-*.jar")), "staged JAR remains in live directory"
        assert not list(server.glob(".hagonoy-restore-*.jar")), "restore staging JAR remains in live directory"
        assert not list(server.parent.glob(".hagonoy-paper-transaction-*")), "temporary rollback directory remains"
        assert not list(server.glob("server.jar.rollback-61-*")), "new persistent rollback JAR remains"
        assert not list(server.glob("server.jar.failed-62-*")), "new persistent failed JAR remains"
        assert "ROLLBACK_JAR=" not in output.getvalue()
        print("[OK] No persistent rollback/failed JAR, no temporary transaction, and non-JAR server contents unchanged.")


def test_install_and_restore_failure():
    with tempfile.TemporaryDirectory(prefix="hsmp-install-restore-failure-") as temporary:
        server, jar = setup(Path(temporary))
        real_replace = module.os.replace

        def fail_jar_replace(source, destination):
            source_name = Path(source).name
            if Path(destination) == jar and (
                source_name.startswith(".hagonoy-paper-")
                or source_name.startswith(".hagonoy-restore-")
            ):
                raise OSError("mock JAR replacement failure")
            return real_replace(source, destination)

        def fake_download(_metadata, destination, _user_agent):
            destination.write_bytes(new_bytes)

        def fake_stop(directory, _session, _port, _timeout):
            set_generation(directory, "stopped", old_version)

        output = io.StringIO()
        error = None
        with patch.object(module, "verify_running_server", return_value=runtime), \
             patch.object(module, "fetch_paper_stable_build", return_value=metadata), \
             patch.object(module, "download_verified_paper_build", side_effect=fake_download), \
             patch.object(module, "stop_managed_server", side_effect=fake_stop), \
             patch.object(module.os, "replace", side_effect=fail_jar_replace), \
             contextlib.redirect_stdout(output):
            try:
                module.update_paper_server(
                    server, "mcserver", 25565, "Done",
                    900, 180, "test-agent (https://example.invalid)",
                    "execute"
                )
            except RuntimeError as exc:
                error = exc

        assert error is not None and "Temporary recovery copy retained" in str(error), error
        assert jar.read_bytes() == old_bytes, "canonical JAR unexpectedly changed"
        transactions = list(server.parent.glob(".hagonoy-paper-transaction-*"))
        assert len(transactions) == 1, "recovery transaction was not retained"
        assert (transactions[0] / "previous-server.jar").read_bytes() == old_bytes
        assert not list(server.glob(".hagonoy-restore-*.jar")), "restore staging JAR leaked into server directory"
        assert not list(server.glob(".hagonoy-paper-*.jar")), "staged download leaked into server directory"
        print("[OK] Double replacement failure retains the external recovery JAR without leaving server-directory staging files.")


print("========== DUAL-HOST PAPER UPDATE TRANSACTION TESTS ==========")
run_case("success", False)
run_case("rollback", True)
test_install_and_restore_failure()
print("[DONE] Dual-host Paper update transaction tests passed.")
PY
