import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader(
    "hsmp_core_cache", str(ROOT / "bin" / "hagonoy-generation")
)
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = module
loader.exec_module(module)


def digest(payload):
    return hashlib.sha256(payload).hexdigest()


def plugin_bytes(name, version, payload):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("plugin.yml", f"name: {name}\nversion: {version}\n")
        archive.writestr("payload.bin", payload)
    return buffer.getvalue()


paper_buffer = io.BytesIO()
with zipfile.ZipFile(paper_buffer, "w") as archive:
    archive.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\n")
paper_payload = paper_buffer.getvalue()
geyser_payload = plugin_bytes("Geyser-Spigot", "2.12.1-SNAPSHOT", b"geyser-cache-fixture")

paper_meta = {
    "build": 249, "name": "paper-26.3-249.jar",
    "url": "https://example.invalid/paper.jar",
    "sha256": digest(paper_payload), "size": len(paper_payload),
}
geyser_meta = {
    "project": "geyser", "version": "2.12.1", "build": 1302,
    "name": "Geyser-Spigot.jar", "sha256": digest(geyser_payload),
    "platform": "spigot", "build_history": [],
}


def fake_paper_download(_metadata, destination, _agent):
    Path(destination).write_bytes(paper_payload)


def fake_geyser_download(_metadata, destination, _agent):
    Path(destination).write_bytes(geyser_payload)


print("========== CACHE MISS: DOWNLOAD, VERIFY, PROMOTE ==========")
with tempfile.TemporaryDirectory(prefix="hsmp-cache-test-") as temporary:
    cache = Path(temporary) / "server-update-downloads"
    output = io.StringIO()
    with patch.object(module, "fetch_paper_stable_build", return_value=paper_meta), \
         patch.object(module, "fetch_geysermc_default_build", return_value=geyser_meta) as lookup, \
         patch.object(module, "download_verified_paper_build", side_effect=fake_paper_download) as paper_download, \
         patch.object(module, "download_verified_geysermc_artifact", side_effect=fake_geyser_download) as geyser_download, \
         patch.object(module, "sync_directory"), \
         contextlib.redirect_stdout(output):
        module.populate_core_artifact_cache(cache, "26.3", {"paper", "geyser"}, "test-agent")

    paper_file = cache / "paper-26.3-249.jar"
    geyser_file = cache / "geyser-2.12.1-1302-spigot.jar"
    assert paper_file.read_bytes() == paper_payload
    assert geyser_file.read_bytes() == geyser_payload
    assert paper_download.call_count == 1
    assert geyser_download.call_count == 1
    assert lookup.call_count == 1 and lookup.call_args.args[0] == "geyser"
    assert not list(cache.glob("*.part")) and not list(cache.glob(".*.part"))
    assert "CACHE_PAPER=DOWNLOADED" in output.getvalue()
    assert "CACHE_GEYSER=DOWNLOADED" in output.getvalue()
    print("[OK] Paper and selected installed Geyser artifacts are verified and atomically promoted.")

    print("========== CACHE HIT: NO RE-DOWNLOAD ==========")
    with patch.object(module, "fetch_paper_stable_build", return_value=paper_meta), \
         patch.object(module, "fetch_geysermc_default_build", return_value=geyser_meta), \
         patch.object(module, "download_verified_paper_build") as paper_download, \
         patch.object(module, "download_verified_geysermc_artifact") as geyser_download, \
         patch.object(module, "sync_directory"), \
         contextlib.redirect_stdout(io.StringIO()):
        module.populate_core_artifact_cache(cache, "26.3", {"paper", "geyser"}, "test-agent")
    assert paper_download.call_count == 0
    assert geyser_download.call_count == 0
    print("[OK] A matching official cache hit is reused without downloading.")

    print("========== CORRUPT CACHE: REPLACE ONLY AFTER VERIFIED TEMP ==========")
    geyser_file.write_bytes(b"corrupt-old-cache")
    original_bad = geyser_file.read_bytes()

    def replace_geyser_after_verify(_metadata, destination, _agent):
        Path(destination).write_bytes(geyser_payload)
        assert geyser_file.read_bytes() == original_bad, (
            "Existing cache file was overwritten before the new candidate was verified."
        )

    with patch.object(module, "fetch_paper_stable_build", return_value=paper_meta), \
         patch.object(module, "fetch_geysermc_default_build", return_value=geyser_meta), \
         patch.object(module, "download_verified_geysermc_artifact", side_effect=replace_geyser_after_verify), \
         patch.object(module, "sync_directory"), \
         contextlib.redirect_stdout(io.StringIO()):
        module.populate_core_artifact_cache(cache, "26.3", {"geyser"}, "test-agent")
    assert geyser_file.read_bytes() == geyser_payload
    assert not list(cache.glob("*.part")) and not list(cache.glob(".*.part"))
    print("[OK] A corrupt prior cache entry is replaced only after its new temporary file passes checksum and descriptor checks.")

print("========== FAIL CLOSED ON UNSAFE INPUT ==========")
with tempfile.TemporaryDirectory(prefix="hsmp-cache-invalid-") as temporary:
    try:
        module.populate_core_artifact_cache(temporary, "not-a-version", {"paper"}, "test-agent")
    except RuntimeError as exc:
        assert "Invalid Minecraft version" in str(exc)
    else:
        raise AssertionError("Invalid Minecraft version was accepted.")
    try:
        module.populate_core_artifact_cache(temporary, "26.3", {"chunky"}, "test-agent")
    except RuntimeError as exc:
        assert "already-installed managed" in str(exc)
    else:
        raise AssertionError("An unrelated plugin cache request was accepted.")

print("[DONE] Core update central-cache tests passed.")
