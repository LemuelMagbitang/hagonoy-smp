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
from pathlib import Path
from unittest.mock import patch

helper = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("hagonoy_generation_paper_plan", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

runtime = {
    "pid": "71212",
    "paper_version": "26.1.2-61-main@8dea6f1",
    "minecraft_version": "26.1.2"
}

metadata = {
    "build": 62,
    "name": "paper-26.1.2-62.jar",
    "url": "https://fill-data.papermc.io/v1/objects/example/paper.jar",
    "sha256": "a" * 64,
    "size": 123456
}

def setup(root):
    server = root / "server"
    (server / "logs").mkdir(parents=True)
    (server / "logs" / "latest.log").write_text(
        "Starting minecraft server version 26.1.2\n"
        "This server is running Paper version 26.1.2-61-main@8dea6f1 (test)\n"
    )
    jar = server / "server.jar"
    jar.write_bytes(b"old server jar fixture")

    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(server, "ubuntu", runtime["paper_version"], "26.1.2")
        module.begin(server, "ubuntu", runtime["paper_version"], "26.1.2")

    return server, jar

print("========== 1. NEW STABLE BUILD PLAN ==========")
with tempfile.TemporaryDirectory() as temporary:
    server, jar = setup(Path(temporary))
    original_jar_hash = hashlib.sha256(jar.read_bytes()).hexdigest()
    original_manifest = (server / module.FILENAME).read_bytes()

    output = io.StringIO()
    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "fetch_paper_stable_build", return_value=metadata), \
         patch.object(module, "stop_managed_server") as stop, \
         patch.object(module, "start_managed_server") as start, \
         contextlib.redirect_stdout(output):
        module.update_paper_server(
            server, "mcserver", 25565, "Done",
            900, 180, "test-agent (https://example.invalid)",
            "plan"
        )

    assert "RESULT=READY_FOR_PAPER_UPDATE" in output.getvalue()
    assert stop.call_count == 0
    assert start.call_count == 0
    assert hashlib.sha256(jar.read_bytes()).hexdigest() == original_jar_hash
    assert (server / module.FILENAME).read_bytes() == original_manifest
    assert not list(server.glob(".hagonoy-paper-*.jar"))

print("[OK] Plan identifies build 62 and changes no server files.")

print()
print("========== 2. ALREADY CURRENT PLAN ==========")
with tempfile.TemporaryDirectory() as temporary:
    server, jar = setup(Path(temporary))
    current_build = dict(metadata, build=61)

    output = io.StringIO()
    with patch.object(module, "verify_running_server", return_value=runtime), \
         patch.object(module, "fetch_paper_stable_build", return_value=current_build), \
         patch.object(module, "stop_managed_server") as stop, \
         contextlib.redirect_stdout(output):
        module.update_paper_server(
            server, "mcserver", 25565, "Done",
            900, 180, "test-agent (https://example.invalid)",
            "plan"
        )

    assert "PAPER_UPDATE=ALREADY_CURRENT" in output.getvalue()
    assert "RESULT=READY_FOR_PAPER_UPDATE" in output.getvalue()
    assert stop.call_count == 0

print("[OK] Already-current build requires no stop or restart.")

print()
print("========== ALL PAPER UPDATE PLAN TESTS PASSED ==========")
PY
