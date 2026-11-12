import contextlib
import importlib.machinery
import importlib.util
import io
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "hsmp_core_host_route", str(ROOT / "bin" / "hagonoy-generation")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

runtime = {
    "pid": "windows-java",
    "paper_version": "26.3-244-main@test",
    "minecraft_version": "26.3",
}
paper_metadata = {
    "build": 244,
    "name": "paper-26.3-244.jar",
    "url": "https://example.invalid/paper.jar",
    "sha256": "a" * 64,
    "size": 100,
}


def make_windows_server(root):
    server = root / "windows-server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.3\n"
        "This server is running Paper version 26.3-244-main@test (test)\n",
        encoding="utf-8",
    )
    (server / "server.jar").write_bytes(b"paper-current")
    (server / "plugins").mkdir()
    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "windows", runtime["paper_version"], "26.3")
        module.begin(server, "windows", runtime["paper_version"], "26.3")
    return server


print("========== WINDOWS GENERATION: READ-ONLY PLAN ==========")
with tempfile.TemporaryDirectory(prefix="hsmp-windows-route-") as temporary:
    server = make_windows_server(Path(temporary))
    manifest = module.load(server)
    calls = []

    def verify(directory, host, paper, minecraft, session, port, **kwargs):
        calls.append((host, kwargs))
        assert host == "windows"
        assert module.load(directory)["host"] == "windows"
        return runtime

    output = io.StringIO()
    with patch.object(module, "verify_running_server", side_effect=verify), \
         patch.object(module, "fetch_paper_stable_build", return_value=paper_metadata), \
         patch.object(module, "inspect_installed_managed_plugins", return_value={}), \
         contextlib.redirect_stdout(output):
        module.update_core_server(
            server, "mcserver", 25565, "Done", 900, 180,
            "test-agent", "plan", host="windows",
            expected_generation_id=manifest["generation_id"],
        )

    assert calls and calls[0][0] == "windows"
    assert "ACTIVE_HOST=WINDOWS" in output.getvalue()
    assert "CORE_UPDATE=ALREADY_CURRENT" in output.getvalue()
    assert module.load(server)["generation_id"] == manifest["generation_id"]
    print("[OK] Windows-running generation is accepted and the read-only plan stays on Windows.")

print("========== STALE GENERATION: REFUSE BEFORE RUNTIME OR UPDATE ==========")
with tempfile.TemporaryDirectory(prefix="hsmp-stale-route-") as temporary:
    server = make_windows_server(Path(temporary))
    with patch.object(module, "verify_running_server") as verify, \
         patch.object(module, "fetch_paper_stable_build") as fetch, \
         patch.object(module, "stop_managed_server") as stop:
        try:
            module.update_core_server(
                server, "mcserver", 25565, "Done", 900, 180,
                "test-agent", "execute", host="windows",
                expected_generation_id="not-the-current-generation",
            )
        except RuntimeError as exc:
            assert "generation changed" in str(exc).lower()
        else:
            raise AssertionError("A stale generation ID was accepted.")
        assert verify.call_count == 0
        assert fetch.call_count == 0
        assert stop.call_count == 0
    print("[OK] Stale generation identity is rejected before runtime discovery, downloads, or shutdown.")

print("[DONE] Windows core updater routing tests passed.")
