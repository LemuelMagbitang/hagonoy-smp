#!/usr/bin/env python3
"""Offline unit checks for HSMP maintenance helpers; no server access or file changes."""
from __future__ import annotations

import io
import json
import tempfile
import tarfile
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

addons = load(ROOT / "bin" / "hagonoy-addons.py")
with tempfile.TemporaryDirectory(prefix="hsmp-config-parse-test-") as tmp:
    root = Path(tmp)
    (root / "config").mkdir()
    (root / "config" / "dual-host.conf").write_text(
        'WINDOWS_TMUX_SESSION="mc-win"\n'
        'UBUNTU_SSH_TARGET="hsmp@ubuntu"\n'
        'UBUNTU_SERVER_DIR="/home/hsmp/minecraft-server"\n'
        'WINDOWS_SERVER_DIR="/mnt/d/Hagonoy-SMP/minecraft-server"\n'
        'UBUNTU_TMUX_SESSION="mc-ubuntu"\n'
        'MINECRAFT_PORT="25565"\n'
        'WINDOWS_BACKUP_DIR="/mnt/d/Hagonoy-SMP/server-backup"\n'
        'UBUNTU_BACKUP_DIR="/home/hsmp/server-backup"\n',
        encoding="utf-8",
    )
    original_root = addons["ROOT"]
    try:
        addons["ROOT"] = root
        values = addons["config_values"]()
        assert len(values) == 8
        assert values[0] == "mc-win" and values[1] == "hsmp@ubuntu"
        assert values[5] == "25565" and values[6].endswith("/server-backup")
    finally:
        addons["ROOT"] = original_root
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

deploy = load(ROOT / "bin" / "hagonoy-addons-deploy.py")

with tempfile.TemporaryDirectory(prefix="hsmp-deploy-test-") as tmp:
    base = Path(tmp)
    server = base / "minecraft-server"
    stage = base / "stage"
    (server / "plugins").mkdir(parents=True)
    (server / "world" / "datapacks").mkdir(parents=True)
    disabled = server / "datapacks-disabled-26.3-test"
    disabled.mkdir()
    (server / "server.properties").write_text("server-port=25565\n")
    (server / "server.jar").write_bytes(b"old paper")
    (server / ".hagonoy-generation.json").write_text(json.dumps({
        "schema_version": 1, "generation": 6, "generation_id": "test",
        "state": "stopped", "host": "ubuntu",
    }))
    old_chunky = server / "plugins" / "Chunky-Bukkit-1.5.3.jar"
    old_chunky.write_bytes(b"old chunky")
    old_double = server / "world" / "datapacks" / "double shulker shells v1.3.15.zip"
    old_double.write_bytes(b"old double shells")
    unknown_active = server / "world" / "datapacks" / "unrelated-custom.zip"
    unknown_active.write_bytes(b"keep this")
    (disabled / "confetti creepers v2.2.16.zip").write_bytes(b"retire this")
    (disabled / "double shulker shells v1.3.15.zip").write_bytes(b"old disabled pack")
    (disabled / "unrelated-disabled.zip").write_bytes(b"keep this too")

    (stage / "plugins").mkdir(parents=True)
    (stage / "datapacks").mkdir(parents=True)
    (stage / "server.jar").write_bytes(b"new verified paper")
    new_chunky = b"new verified chunky"
    (stage / "plugins" / "Chunky-Paper-1.5.66.jar").write_bytes(new_chunky)
    new_double = b"new double shells"
    new_painting = b"new painting picker"
    (stage / "datapacks" / "double shulker shells v1.3.18.zip").write_bytes(new_double)
    (stage / "datapacks" / "painting picker v1.1.5 (MC 26.3).zip").write_bytes(new_painting)
    sha = lambda data: __import__("hashlib").sha256(data).hexdigest()
    manifest = {
        "source_host": "ubuntu",
        "paper": {"sha256": sha(b"new verified paper")},
        "plugins": [{
            "name": "Chunky",
            "filename": "Chunky-Paper-1.5.66.jar",
            "sha256": sha(new_chunky),
            "remove_files": ["Chunky-Bukkit-1.5.3.jar"],
        }],
        "datapacks": [
            {"key": "double shulker shells", "filename": "double shulker shells v1.3.18.zip", "sha256": sha(new_double)},
            {"key": "painting picker", "filename": "painting picker v1.1.5 (MC 26.3).zip", "sha256": sha(new_painting)},
        ],
        "known_vanilla_tweaks_keys": [
            "double shulker shells", "confetti creepers", "painting picker"
        ],
        "retired_keys": ["confetti creepers"],
    }
    (stage / "update-manifest.json").write_text(json.dumps(manifest))
    deploy["apply_staged_changes"](server, stage)

    assert (server / "server.jar").read_bytes() == b"new verified paper"
    assert not old_chunky.exists()
    assert (server / "plugins" / "Chunky-Paper-1.5.66.jar").read_bytes() == new_chunky
    assert not old_double.exists()
    assert (server / "world" / "datapacks" / "double shulker shells v1.3.18.zip").read_bytes() == new_double
    assert (server / "world" / "datapacks" / "painting picker v1.1.5 (MC 26.3).zip").read_bytes() == new_painting
    assert unknown_active.read_bytes() == b"keep this"
    assert not (disabled / "confetti creepers v2.2.16.zip").exists()
    assert not (disabled / "double shulker shells v1.3.15.zip").exists()
    assert (disabled / "unrelated-disabled.zip").read_bytes() == b"keep this too"

    running = base / "running-server"
    shutil = __import__("shutil")
    shutil.copytree(server, running)
    running_manifest = json.loads((running / ".hagonoy-generation.json").read_text())
    running_manifest["state"] = "running"
    (running / ".hagonoy-generation.json").write_text(json.dumps(running_manifest))
    try:
        deploy["apply_staged_changes"](running, stage)
    except RuntimeError as exc:
        assert "not STOPPED" in str(exc)
    else:
        raise AssertionError("A RUNNING generation accepted file replacement")

with tempfile.TemporaryDirectory(prefix="hsmp-unsafe-backup-test-") as tmp:
    archive_path = Path(tmp) / "unsafe.tar"
    with tarfile.open(archive_path, "w") as archive:
        import tarfile as tar_module
        info = tar_module.TarInfo("../escape.txt")
        info.size = 0
        archive.addfile(info)
    try:
        deploy["safe_archive_members"](archive_path)
    except RuntimeError as exc:
        assert "Unsafe path" in str(exc)
    else:
        raise AssertionError("Unsafe archive path was accepted")

with tempfile.TemporaryDirectory(prefix="hsmp-lock-test-") as tmp:
    fake_dir = Path(tmp)
    original_run = deploy["subprocess"].run
    seen = []
    class Result:
        def __init__(self, returncode=0, stdout="", stderr=""):
            self.returncode, self.stdout, self.stderr = returncode, stdout, stderr
    def fake_run(args, **kwargs):
        seen.append(args)
        if args[:2] == ["tmux", "has-session"]:
            return Result(returncode=1)
        if args and args[0] == "ss":
            return Result(returncode=0, stdout="")
        raise AssertionError(f"Unexpected runtime probe: {args}")
    try:
        deploy["subprocess"].run = fake_run
        deploy["assert_runtime_stopped"]("ubuntu", "mcserver", "25565")
        try:
            deploy["fail"]("rollback handler test")
        except RuntimeError as exc:
            assert "rollback handler test" in str(exc)
        else:
            raise AssertionError("Deployment fail() did not raise a rollback-catchable exception")
    finally:
        deploy["subprocess"].run = original_run
    assert len(seen) == 2

try:
    deploy["run_stream"]([__import__("sys").executable, "-c", "import time; time.sleep(0.25)"], timeout=2)
except Exception as exc:
    raise AssertionError(f"Quiet child process should complete before timeout: {exc}")
try:
    deploy["run_stream"]([__import__("sys").executable, "-c", "import time; time.sleep(0.5)"], timeout=0.1)
except RuntimeError as exc:
    assert "safety timeout" in str(exc)
else:
    raise AssertionError("Quiet child process did not obey the no-output timeout")

print("[OK] World-border targets and no-shrink policy constants")
print("[OK] Eight-field dual-host config NUL parser")
print("[OK] PaperMC stable-build size and SHA-256 verification")
print("[OK] Chunky, Geyser and Floodgate publisher metadata verification")
print("[OK] Version comparison and VanillaTweaks filename reconciliation")
print("[OK] Nested datapack ZIP and 26.3 pack-format inspection")
print("[OK] Backup-first staged deployment, old-pack retirement and unknown-pack preservation")
print("[OK] Refuse file replacement while generation is RUNNING")
print("[OK] Reject unsafe TAR paths before rollback extraction")
print("[OK] Lock/stopped-state guard for host maintenance")
print("[OK] No-output command timeout and rollback-catchable failure propagation")
