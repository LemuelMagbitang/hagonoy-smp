#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$ROOT/bin/hagonoy-generation" <<'PY'
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

loader = importlib.machinery.SourceFileLoader("hsmp_core_api", sys.argv[1])
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

agent = "HSMP-test"
old_bytes = b"old official fixture"
new_bytes = b"new official fixture"
old_sha = hashlib.sha256(old_bytes).hexdigest()
new_sha = hashlib.sha256(new_bytes).hexdigest()

build_payload = {
    "project_id": "geyser",
    "version": "2.12.1",
    "builds": [
        {"build": 1300, "channel": "default", "promoted": False,
         "downloads": {"spigot": {"name": "Geyser-Spigot.jar", "sha256": new_sha}}},
        {"build": 1301, "channel": "experimental", "promoted": False,
         "downloads": {"spigot": {"name": "Geyser-Spigot.jar", "sha256": "f" * 64}}},
        {"build": 1295, "channel": "default", "promoted": False,
         "downloads": {"spigot": {"name": "Geyser-Spigot.jar", "sha256": old_sha}}},
    ],
}
latest_payload = {"project_id": "geyser", "version": "2.12.1", "build": 1301}

responses = iter([
    io.BytesIO(json.dumps(latest_payload).encode()),
    io.BytesIO(json.dumps(build_payload).encode()),
])
with patch.object(module.urllib.request, "urlopen", side_effect=lambda *a, **k: next(responses)):
    metadata = module.fetch_geysermc_default_build("geyser", agent)

assert metadata["build"] == 1300, metadata
assert metadata["channel"] == "default"
assert metadata["sha256"] == new_sha
assert metadata["name"] == "Geyser-Spigot.jar"
assert metadata["url"].endswith("/1300/downloads/spigot")
print("[OK] Latest default-channel build selected; experimental ignored even though it has a higher build number.")

floodgate_sha = hashlib.sha256(b"official Floodgate 2.2.5 build 141").hexdigest()
floodgate_latest = {"project_id": "floodgate", "version": "2.2.5", "build": 142}
floodgate_builds = {
    "project_id": "floodgate", "version": "2.2.5", "builds": [
        {"build": 141, "channel": "default", "downloads": {
            "spigot": {"name": "floodgate-spigot.jar", "sha256": floodgate_sha}}},
        {"build": 142, "channel": "experimental", "downloads": {
            "spigot": {"name": "floodgate-spigot.jar", "sha256": "d" * 64}}},
    ],
}
responses = iter([
    io.BytesIO(json.dumps(floodgate_latest).encode()),
    io.BytesIO(json.dumps(floodgate_builds).encode()),
])
with patch.object(module.urllib.request, "urlopen", side_effect=lambda *a, **k: next(responses)):
    floodgate_metadata = module.fetch_geysermc_default_build("floodgate", agent)
assert floodgate_metadata["build"] == 141
assert floodgate_metadata["name"] == "floodgate-spigot.jar"
assert floodgate_metadata["sha256"] == floodgate_sha
print("[OK] Floodgate selects the Spigot default-channel artifact and its checksum.")

print("========== VERIFY INSTALLED RELEASE IDENTITY ==========")
old_release_payload = {
    "project_id": "geyser",
    "version": "2.12.0",
    "builds": [
        {"build": 1280, "channel": "default", "downloads": {
            "spigot": {"name": "Geyser-Spigot.jar", "sha256": old_sha}}},
        {"build": 1281, "channel": "experimental", "downloads": {
            "spigot": {"name": "Geyser-Spigot.jar", "sha256": "e" * 64}}},
    ],
}
with patch.object(module.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(old_release_payload).encode())) as api:
    old_history = module.fetch_geysermc_default_builds("geyser", "2.12.0", agent)
assert len(old_history) == 1 and old_history[0]["build"] == 1280
assert api.call_args.args[0].full_url.endswith("/geyser/versions/2.12.0/builds")
installed_old = {"project": "geyser", "version": "2.12.0-SNAPSHOT", "sha256": old_sha}
metadata_current = dict(metadata, project="geyser", version="2.12.1", build=1300, platform="spigot")
with patch.object(module, "fetch_geysermc_default_builds", return_value=old_history):
    assert module.plugin_needs_update(installed_old, metadata_current, agent)
with patch.object(module, "fetch_geysermc_default_builds", return_value=old_history):
    try:
        module.plugin_needs_update(dict(installed_old, sha256="c" * 64), metadata_current, agent)
    except RuntimeError as exc:
        assert "not recognized" in str(exc)
    else:
        raise AssertionError("An unrecognized/custom older plugin JAR was accepted.")
module.ensure_geyser_paper_compatibility("26.3")
try:
    module.ensure_geyser_paper_compatibility("1.20.4")
except RuntimeError as exc:
    assert "1.20.5 or newer" in str(exc)
else:
    raise AssertionError("Unsupported old Paper version was accepted for Geyser update.")
print("[OK] Older installed plugins must match their own official release history; custom hashes are rejected, and Geyser compatibility is gated.")

class FakeResponse(io.BytesIO):
    def __init__(self, content):
        super().__init__(content)
        self.headers = {"Content-Length": str(len(content))}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()

with tempfile.TemporaryDirectory() as temporary:
    destination = Path(temporary) / "geyser.part"
    download_metadata = dict(metadata, sha256=new_sha)
    with patch.object(module.urllib.request, "urlopen", return_value=FakeResponse(new_bytes)):
        module.download_verified_geysermc_artifact(download_metadata, destination, agent)
    assert destination.read_bytes() == new_bytes
    print("[OK] GeyserMC artifact download is SHA-256 verified.")

with tempfile.TemporaryDirectory() as temporary:
    destination = Path(temporary) / "geyser.part"
    download_metadata = dict(metadata, sha256="0" * 64)
    with patch.object(module.urllib.request, "urlopen", return_value=FakeResponse(new_bytes)):
        try:
            module.download_verified_geysermc_artifact(download_metadata, destination, agent)
        except RuntimeError as exc:
            assert "SHA-256" in str(exc)
        else:
            raise AssertionError("Bad Geyser checksum was accepted.")
    assert not destination.exists()
    print("[OK] GeyserMC checksum mismatch removes the staged file and fails closed.")

print("========== PAPER PLUGIN VERSION RESPONSE ==========")
from unittest.mock import call
with patch.object(module, "run_command", side_effect=[
    "[12:00:00 INFO]: Previous console output\n",
    "",
    "[12:00:01 INFO]: Geyser-Spigot version 2.12.1-SNAPSHOT\n",
]) as command:
    result = module.query_plugin_version_from_console(
        "mcserver", "Geyser-Spigot", "2.12.1-SNAPSHOT", timeout=1
    )
assert result == "2.12.1-SNAPSHOT"
assert command.call_count == 3
assert command.call_args_list[1].args[0][-2] == "version Geyser-Spigot"
print("[OK] Runtime verifier accepts Paper's direct 'PluginName version X' response, without expecting the unrelated server-version marker.")

print("[DONE] Core updater API tests passed.")
PY
