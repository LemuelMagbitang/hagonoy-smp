#!/usr/bin/env python3
"""Offline unit checks for HSMP maintenance helpers; no server access or file changes."""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load(path: Path):
    namespace = {"__name__": "_hsmp_test_module", "__file__": str(path)}
    source = path.read_text(encoding="utf-8")
    exec(compile(source, str(path), "exec"), namespace)
    return namespace


border = load(ROOT / "bin" / "hagonoy-world-border.py")
assert border["TARGETS"]["minecraft:overworld"]["diameter"] == 12500
assert border["TARGETS"]["minecraft:overworld"]["center"] == ("-2349", "38")
assert border["TARGETS"]["minecraft:the_nether"]["diameter"] == 3125
assert border["TARGETS"]["minecraft:the_nether"]["center"] == ("-293.625", "4.75")
assert border["TARGETS"]["minecraft:the_end"]["diameter"] == 20000
assert border["TARGETS"]["minecraft:the_end"]["change_diameter"] is False
assert border["WIDTH_RE"].search("The world border is currently 10000 blocks wide")
assert border["WIDTH_RE"].search("The world border is currently 10000 block wide")
assert border["WIDTH_RE"].search("The world border is currently 10000 block(s) wide").group(1) == "10000"
assert border["WIDTH_RE"].search("The world border is currently 10000.0 blocks wide").group(1) == "10000.0"
assert border["WIDTH_RE"].search("The world border is currently 1.25E+04 block(s) wide").group(1) == "1.25E+04"


addons = load(ROOT / "bin" / "hagonoy-addons.py")
assert addons["pack_key"]("painting picker v1.1.5 (MC 26.3).zip") == "painting picker"
assert addons["compare_versions"]("1.5.66", "1.5.3") == "candidate is newer"
assert addons["compare_versions"]("1.5.3", "1.5.66") == "candidate is older; do not downgrade"
assert addons["format_pair"]([121, 0]) == (121, 0)

def make_pack(format_version: int) -> bytes:
    target = io.BytesIO()
    metadata = {"pack": {"min_format": [format_version, 0], "max_format": [format_version, 0]}}
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("pack.mcmeta", json.dumps(metadata))
        archive.writestr("data/example/functions/test.mcfunction", "say test\n")
    return target.getvalue()

with tempfile.TemporaryDirectory(prefix="hsmp-paper-test-") as tmp:
    artifact = Path(tmp) / "paper-26.3-244.jar"
    with zipfile.ZipFile(artifact, "w", zipfile.ZIP_DEFLATED) as jar:
        jar.writestr("META-INF/MANIFEST.MF", "Manifest-Version: 1.0\\n")
        jar.writestr("paper-test.txt", "stable build test")
    digest = addons["sha256_file"](artifact)
    expected = {
        "channel": "STABLE",
        "id": 244,
        "downloads": {
            "server:default": {
                "size": artifact.stat().st_size,
                "checksums": {"sha256": digest},
            }
        },
    }
    import urllib.request
    original = urllib.request.urlopen
    try:
        urllib.request.urlopen = lambda request, timeout=20: io.BytesIO(json.dumps([expected]).encode())
        verified, detail = addons["official_paper_candidate"](artifact, "26.3", 244)
        assert verified and "SHA-256 verified" in detail
        expected["downloads"]["server:default"]["checksums"]["sha256"] = "0" * 64
        verified, detail = addons["official_paper_candidate"](artifact, "26.3", 244)
        assert not verified and "SHA-256 mismatch" in detail
    finally:
        urllib.request.urlopen = original

with tempfile.TemporaryDirectory(prefix="hsmp-plugin-test-") as tmp:
    chunky = Path(tmp) / "Chunky-Paper-1.5.66.jar"
    with zipfile.ZipFile(chunky, "w", zipfile.ZIP_DEFLATED) as jar:
        jar.writestr("plugin.yml", "name: Chunky\\nversion: 1.5.66\\n")
    digest = addons["sha256_file"](chunky)
    original_fetch = addons["fetch_json"]
    try:
        addons["fetch_json"] = lambda url: [{
            "version_type": "release",
            "version_number": "1.5.66",
            "date_published": "2026-11-04T00:00:00Z",
            "files": [{
                "filename": chunky.name,
                "hashes": {"sha256": digest},
            }],
        }]
        verified, detail = addons["official_chunky_candidate"](chunky, "1.5.66", digest)
        assert verified and "Minecraft 26.3" in detail

        for project, filename in (
            ("geyser", "Geyser-Spigot.jar"),
            ("floodgate", "floodgate-spigot.jar"),
        ):
            artifact = Path(tmp) / filename
            artifact.write_bytes(b"publisher test artifact")
            artifact_hash = addons["sha256_file"](artifact)
            addons["fetch_json"] = lambda url, n=filename, h=artifact_hash: {
                "version": "test-snapshot",
                "builds": [{
                    "build": 1276,
                    "channel": "default",
                    "promoted": True,
                    "downloads": {"spigot": {"name": n, "sha256": h}},
                }],
            }
            verified, detail = addons["official_geysermc_candidate"](project, artifact, artifact_hash)
            assert verified and "SHA-256 verified" in detail
    finally:
        addons["fetch_json"] = original_fetch

with tempfile.TemporaryDirectory(prefix="hsmp-addon-test-") as tmp:
    bundle = Path(tmp) / "VanillaTweaks_d831085_UNZIP_ME.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("painting picker v1.1.5 (MC 26.3).zip", make_pack(121))
        outer.writestr("old pack v1.0 (MC old).zip", make_pack(120))
    packs = addons["read_bundle"](bundle)
    assert packs["painting picker"]["compatible"] is True
    assert packs["old pack"]["compatible"] is False

    nested = io.BytesIO()
    with zipfile.ZipFile(nested, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("nested/pack.mcmeta", json.dumps({"pack": {"pack_format": 121}}))
    with zipfile.ZipFile(io.BytesIO(nested.getvalue())) as archive:
        compatible, reason = addons["pack_metadata"](archive)
        assert compatible is False and "nested below" in reason

print("[OK] World-border targets, no-shrink policy, and console reply parsing")
print("[OK] PaperMC stable-build size and SHA-256 verification")
print("[OK] Chunky, Geyser and Floodgate publisher metadata verification")
print("[OK] Version comparison and VanillaTweaks filename reconciliation")
print("[OK] Nested datapack ZIP and 26.3 pack-format inspection")
