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
loader = importlib.machinery.SourceFileLoader("hagonoy_generation", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

verified = {
    "directory": None,
    "pid": "4242",
    "paper_version": "26.1.2-61-main@8dea6f1",
    "minecraft_version": "26.1.2"
}

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    ubuntu = root / "ubuntu"
    ubuntu.mkdir()

    verified["directory"] = str(ubuntu)

    print("========== 1. INITIAL RUNNING GENERATION ==========")
    with patch.object(module, "verify_running_server", return_value=verified):
        with contextlib.redirect_stdout(io.StringIO()):
            module.adopt_running(
                ubuntu, "ubuntu", "AUTO", "AUTO", "mcserver", 25565
            )

    manifest = ubuntu / module.FILENAME
    data = json.loads(manifest.read_text())

    assert data["generation"] == 1
    assert data["state"] == "running"
    assert data["host"] == "ubuntu"
    assert data["paper_version"] == verified["paper_version"]
    assert data["minecraft_version"] == verified["minecraft_version"]
    assert data["parent_generation_id"] is None
    assert data["ancestors"] == []
    assert data["started_at_utc"] is not None
    assert data["stopped_at_utc"] is None
    assert data["generation_id"]

    print("[OK] Generation 1 recorded as RUNNING.")

    print()
    print("========== 2. EXISTING MANIFEST PROTECTION ==========")
    before = digest(manifest)

    with patch.object(module, "verify_running_server", return_value=verified):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                module.adopt_running(
                    ubuntu, "ubuntu", "AUTO", "AUTO", "mcserver", 25565
                )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Repeated adoption unexpectedly succeeded.")

    assert digest(manifest) == before
    print("[OK] Existing manifest retained unchanged.")

    print()
    print("========== 3. STOPPED MANIFEST PROTECTION ==========")
    stopped = root / "stopped"
    stopped.mkdir()

    with contextlib.redirect_stdout(io.StringIO()):
        module.seal(stopped, "ubuntu", "test-paper", "test-minecraft")

    stopped_manifest = stopped / module.FILENAME
    before = digest(stopped_manifest)

    verified["directory"] = str(stopped)

    with patch.object(module, "verify_running_server", return_value=verified):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                module.adopt_running(
                    stopped, "ubuntu", "AUTO", "AUTO", "mcserver", 25565
                )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Stopped generation was overwritten.")

    assert digest(stopped_manifest) == before
    print("[OK] Stopped generation retained unchanged.")

print()
print("========== ALL ADOPTION TESTS PASSED ==========")
PY
