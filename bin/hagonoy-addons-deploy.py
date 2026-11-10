#!/usr/bin/env python3
"""Backup-first, plan-validated HSMP Paper/plugin/datapack deployment."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import runpy
import select
import shlex
import signal
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
ADDONS_FILE = ROOT / "bin" / "hagonoy-addons.py"
BACKUP_SCRIPT = ROOT / "bin" / "hagonoy-dual-backup"
LIFECYCLE_UBUNTU = ROOT / "bin" / "hagonoy-dual-lifecycle"
LIFECYCLE_WINDOWS = ROOT / "bin" / "hagonoy-dual-windows-lifecycle"
DOWNLOADS = Path("/mnt/d/Hagonoy-SMP/server-update-downloads")
PRIMARY_BUNDLE = "VanillaTweaks_d831085_UNZIP_ME.zip"

KNOWN_VANILLA_TWEAKS = {
    "durability ping",
    "afk display",
    "silence mobs",
    "villager workstation highlights",
    "confetti creepers",
    "more mob heads",
    "multiplayer sleep",
    "chunk loaders",
    "name colors",
    "player head drops",
    "double shulker shells",
    "anti enderman grief",
    "painting picker",
    "track statistics",
    "track raw statistics",
}

def fail(message: str) -> "NoReturn":
    raise RuntimeError(message)


def run(args: list[str], *, input_text: str | None = None, timeout: int = 60) -> str:
    try:
        result = subprocess.run(
            args, input=input_text, text=True, capture_output=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Could not run {args[0]}: {exc}")
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        fail(f"{args[0]} failed: {detail or result.returncode}")
    return result.stdout.strip()


def run_stream(args: list[str], *, timeout: int = 3600) -> str:
    try:
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=False, bufsize=0,
        )
    except OSError as exc:
        fail(f"Could not start {args[0]}: {exc}")
    assert process.stdout is not None
    fd = process.stdout.fileno()
    decoder = __import__("codecs").getincrementaldecoder("utf-8")("replace")
    output: list[str] = []
    started = time.monotonic()
    try:
        while True:
            remaining = timeout - (time.monotonic() - started)
            if remaining <= 0:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                fail(f"{args[0]} exceeded its {timeout}-second safety timeout.")
            readable, _, _ = select.select([fd], [], [], min(0.5, remaining))
            if readable:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                decoded = decoder.decode(chunk)
                if decoded:
                    output.append(decoded)
                    print(decoded, end="", flush=True)
            elif process.poll() is not None:
                # Do not perform a blocking read after the direct child has exited;
                # a detached descendant could still hold the pipe open.
                break
        tail = decoder.decode(b"", final=True)
        if tail:
            output.append(tail)
            print(tail, end="", flush=True)
        code = process.wait(timeout=5)
    except Exception:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        raise
    finally:
        process.stdout.close()
    if code:
        fail(f"{args[0]} returned exit code {code}.")
    return "".join(output)


def addons_module() -> dict[str, Any]:
    if not ADDONS_FILE.is_file():
        fail(f"Missing addon inventory helper: {ADDONS_FILE}")
    return runpy.run_path(str(ADDONS_FILE))


def pack_key(filename: str) -> str:
    stem = Path(filename).stem
    return re.sub(r"\s+v\d.*$", "", stem, flags=re.IGNORECASE).strip().casefold()


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_copy(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(f".{destination.name}.hsmp-new-{uuid.uuid4().hex}")
    try:
        shutil.copy2(source, temp)
        with temp.open("rb") as stream:
            os.fsync(stream.fileno())
        os.replace(temp, destination)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def validate_staged_file(path: Path, expected_sha: str) -> None:
    if not path.is_file() or path.is_symlink():
        fail(f"Staged update file is missing or not a regular file: {path}")
    digest = sha256_path(path)
    if digest.casefold() != expected_sha.casefold():
        fail(f"Staged update SHA-256 mismatch: {path.name}")


def assert_runtime_stopped(host: str, session: str, port: str) -> None:
    session_result = subprocess.run(
        ["tmux", "has-session", "-t", f"={session}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if session_result.returncode == 0:
        raise RuntimeError("Managed Minecraft tmux session still exists; refusing file maintenance.")
    if session_result.returncode != 1:
        raise RuntimeError("Could not reliably establish tmux state; refusing file maintenance.")

    if host == "ubuntu":
        probe = subprocess.run(
            ["ss", "-H", "-ltn", f"sport = :{int(port)}"],
            text=True, capture_output=True, check=False,
        )
        if probe.returncode != 0 or probe.stdout.strip():
            raise RuntimeError("Ubuntu Minecraft TCP listener remains active or uncertain.")
    elif host == "windows":
        command = (
            f"$c=Get-NetTCPConnection -State Listen -LocalPort {int(port)} "
            "-ErrorAction SilentlyContinue; if ($c) {'RUNNING'} else {'STOPPED'}"
        )
        probe = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            text=True, capture_output=True, timeout=12, check=False,
        )
        if probe.returncode != 0 or probe.stdout.strip() != "STOPPED":
            raise RuntimeError("Windows Minecraft TCP listener remains active or uncertain.")
    else:
        raise RuntimeError(f"Unsupported maintenance host: {host}")


def with_maintenance_lock(host: str, operation, *args):
    lock_path = (
        "/tmp/hagonoy-smp-lifecycle.lock"
        if host == "ubuntu"
        else "/tmp/hagonoy-smp-windows-lifecycle.lock"
    )
    try:
        with open(lock_path, "a", encoding="utf-8") as lock_file:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return operation(*args)
    except BlockingIOError as exc:
        raise RuntimeError("Another HSMP lifecycle or maintenance operation holds the host lock.") from exc


def locked_apply_staged_changes(
    server_dir: Path, stage_dir: Path, host: str, session: str, port: str
) -> None:
    def operation() -> None:
        assert_runtime_stopped(host, session, port)
        apply_staged_changes(server_dir, stage_dir)

    with_maintenance_lock(host, operation)


def apply_staged_changes(server_dir: Path, stage_dir: Path) -> None:
    server_dir = server_dir.resolve(strict=True)
    stage_dir = stage_dir.resolve(strict=True)
    manifest_path = stage_dir / "update-manifest.json"
    data = json.loads(manifest_path.read_text(encoding="utf-8"))

    generation_path = server_dir / ".hagonoy-generation.json"
    generation = json.loads(generation_path.read_text(encoding="utf-8"))
    if generation.get("state") != "stopped":
        raise RuntimeError("Canonical generation manifest is not STOPPED; refusing file changes.")
    if generation.get("host") != data["source_host"].casefold():
        raise RuntimeError("Stopped generation host does not match the selected source host.")
    if not (server_dir / "server.properties").is_file():
        raise RuntimeError("Canonical directory is missing server.properties.")

    paper = data.get("paper")
    if paper:
        source = stage_dir / "server.jar"
        validate_staged_file(source, paper["sha256"])
        atomic_copy(source, server_dir / "server.jar")
        print("PAPER_JAR=REPLACED")

    plugin_dir = server_dir / "plugins"
    for plugin in data.get("plugins", []):
        filename = plugin["filename"]
        if Path(filename).name != filename or filename in {"", ".", ".."}:
            raise RuntimeError(f"Unsafe plugin filename in update plan: {filename}")
        source = stage_dir / "plugins" / filename
        validate_staged_file(source, plugin["sha256"])
        atomic_copy(source, plugin_dir / filename)
        for old_name in plugin.get("remove_files", []):
            if Path(old_name).name != old_name:
                raise RuntimeError(f"Unsafe old plugin filename: {old_name}")
            old_path = plugin_dir / old_name
            if old_path != plugin_dir / filename and old_path.is_file() and not old_path.is_symlink():
                old_path.unlink()
        print(f"PLUGIN={plugin['name']}:{plugin['version']}")

    desired = data.get("datapacks", [])
    desired_by_key = {item["key"]: item for item in desired}
    desired_keys = set(desired_by_key)
    known_keys = set(data.get("known_vanilla_tweaks_keys", []))
    datapack_dir = server_dir / "world" / "datapacks"
    datapack_dir.mkdir(parents=True, exist_ok=True)

    for old in datapack_dir.glob("*.zip"):
        key = pack_key(old.name)
        if key not in known_keys:
            continue
        wanted = desired_by_key.get(key)
        if wanted is None:
            old.unlink()
        elif old.name != wanted["filename"] or sha256_path(old) != wanted["sha256"]:
            old.unlink()

    for disabled in server_dir.glob("datapacks-disabled*"):
        if not disabled.is_dir() or disabled.is_symlink():
            continue
        for old in disabled.glob("*.zip"):
            if pack_key(old.name) in known_keys and old.is_file() and not old.is_symlink():
                old.unlink()
        try:
            disabled.rmdir()
        except OSError:
            # Keep the directory if it contains unrelated material.
            pass

    for item in desired:
        filename = item["filename"]
        if Path(filename).name != filename or filename in {"", ".", ".."}:
            raise RuntimeError(f"Unsafe datapack filename in update plan: {filename}")
        source = stage_dir / "datapacks" / filename
        validate_staged_file(source, item["sha256"])
        destination = datapack_dir / filename
        if not destination.is_file() or sha256_path(destination) != item["sha256"]:
            atomic_copy(source, destination)

    actual_selected = {pack_key(path.name) for path in datapack_dir.glob("*.zip")}
    missing = sorted(desired_keys - actual_selected)
    if missing:
        raise RuntimeError("Datapack installation verification failed: " + ", ".join(missing))

    print(f"DATAPACKS_INSTALLED={len(desired)}")
    print(f"RETIRED_VANILLA_TWEAKS={','.join(data.get('retired_keys', [])) or 'none'}")


def safe_archive_members(archive_path: Path) -> None:
    try:
        with tarfile.open(archive_path, "r:*") as archive:
            for member in archive.getmembers():
                name = member.name.replace("\\", "/")
                parts = [part for part in name.split("/") if part not in ("", ".")]
                if name.startswith("/") or ".." in parts:
                    raise RuntimeError(f"Unsafe path in backup archive: {member.name}")
                if member.issym() or member.islnk():
                    link = member.linkname.replace("\\", "/")
                    link_parts = [part for part in link.split("/") if part not in ("", ".")]
                    if link.startswith("/") or ".." in link_parts:
                        raise RuntimeError(f"Unsafe link in backup archive: {member.name} -> {member.linkname}")
    except (OSError, tarfile.TarError) as exc:
        raise RuntimeError(f"Cannot validate backup archive: {exc}") from exc


def locked_restore_archive_local(
    archive_path: Path, server_dir: Path, host: str, session: str, port: str,
    expected_sha256: str | None = None,
) -> None:
    def operation() -> None:
        assert_runtime_stopped(host, session, port)
        restore_archive_local(archive_path, server_dir, expected_sha256)

    with_maintenance_lock(host, operation)


def restore_archive_local(
    archive_path: Path, server_dir: Path, expected_sha256: str | None = None
) -> None:
    server_dir = server_dir.resolve(strict=True)
    archive_path = archive_path.resolve(strict=True)
    if expected_sha256 and sha256_path(archive_path).casefold() != expected_sha256.casefold():
        raise RuntimeError("Rollback TAR SHA-256 no longer matches the verified pre-update archive.")
    safe_archive_members(archive_path)
    stage = Path(tempfile.mkdtemp(
        prefix=".hagonoy-full-restore-", dir=str(server_dir.parent)
    ))
    try:
        print("[hagonoy-update] Extracting verified pre-update archive for full rollback...")
        if shutil.which("pv"):
            run_stream([
                "bash", "-o", "pipefail", "-c",
                'pv -s "$1" "$2" | tar -xf - -C "$3"',
                "hsmp-restore",
                str(archive_path.stat().st_size),
                str(archive_path),
                str(stage),
            ], timeout=1800)
        else:
            print("[hagonoy-update] pv unavailable; extracting with tar (phase-only progress).")
            run_stream(["tar", "-xf", str(archive_path), "-C", str(stage)], timeout=1800)
        run_stream([
            "rsync", "-rlt", "--no-perms", "--no-owner", "--no-group",
            "--info=progress2", "--delete", str(stage) + "/", str(server_dir) + "/",
        ], timeout=1800)
        if not (server_dir / "server.properties").is_file():
            raise RuntimeError("Full rollback copy is missing server.properties.")
        manifest = json.loads(
            (server_dir / ".hagonoy-generation.json").read_text(encoding="utf-8")
        )
        if manifest.get("state") != "stopped":
            raise RuntimeError("Restored generation manifest is not STOPPED.")
    finally:
        shutil.rmtree(stage, ignore_errors=True)





def stream_backup(args: list[str]) -> str:
    return run_stream(args, timeout=2400)


def source_states(a: dict[str, Any], config: tuple[str, ...]) -> tuple[str, str, str]:
    win_session, target, ubuntu_dir, windows_dir, ubu_session, port, _win_backup_dir, _ubu_backup_dir = config
    win = a["windows_state"](win_session, port)
    ubu = a["ubuntu_state"](target, ubu_session, port)
    if win == "UNKNOWN" or ubu == "UNKNOWN":
        fail("A canonical host is uncertain; no update can proceed.")
    if win == "RUNNING" and ubu == "RUNNING":
        fail("Both canonical servers appear to be running; refusing to update either.")
    if win == "STOPPED" and ubu == "STOPPED":
        fail("Both canonical servers are stopped; the authoritative live copy cannot be identified.")
    host = "UBUNTU" if ubu == "RUNNING" else "WINDOWS"
    return host, win, ubu


def build_update_plan(a: dict[str, Any], host: str, facts: dict[str, Any]) -> dict[str, Any]:
    files = sorted(path for path in DOWNLOADS.iterdir() if path.is_file())
    by_name = {path.name.casefold(): path for path in files}
    primary_path = by_name.get(PRIMARY_BUNDLE.casefold())
    if primary_path is None:
        fail(f"Selected VanillaTweaks bundle is missing: {PRIMARY_BUNDLE}")

    primary = a["read_bundle"](primary_path)
    if not primary:
        fail("Selected VanillaTweaks bundle contains no individual datapack ZIPs.")
    blocked = [item["filename"] for item in primary.values() if not item["compatible"]]
    if blocked:
        fail("Datapacks are not verified for 26.3 format 121.0: " + ", ".join(blocked))

    paper_update = None
    paper_candidates = [p for p in files if a["PAPER_RE"].match(p.name)]
    if len(paper_candidates) > 1:
        fail("Multiple Paper candidate JARs are present; leave only the intended Paper build.")
    if paper_candidates:
        path = paper_candidates[0]
        match = a["PAPER_RE"].match(path.name)
        assert match is not None
        version, build = match.group(1), int(match.group(2))
        current = a["paper_current_version"](facts.get("paper_line", ""))
        if current is None:
            fail("Installed Paper version/build could not be established from the server log.")
        if version != current[0]:
            fail(
                f"Paper download is Minecraft {version}, but the installed server is {current[0]}. "
                "Minecraft world upgrades need a separate migration plan."
            )
        current_jar = facts.get("paper_jar")
        if not current_jar:
            fail("Installed server.jar could not be read; refusing to replace Paper.")
        candidate_hash = a["sha256_file"](path)
        if build < current[1]:
            fail(f"Paper candidate build {build} is older than installed build {current[1]}.")
        if build == current[1] and candidate_hash != current_jar["sha256"]:
            fail("Paper reports the installed build number but has a different binary hash.")
        verified, detail = a["official_paper_candidate"](path, version, build)
        if not verified:
            fail("Paper candidate is not the latest verified stable artifact: " + detail)
        if candidate_hash != current_jar["sha256"]:
            paper_update = {
                "source": str(path),
                "sha256": candidate_hash,
                "minecraft_version": version,
                "build": build,
                "detail": detail,
            }

    installed_plugins = facts.get("plugins", [])
    plugin_updates: list[dict[str, Any]] = []
    candidate_specs = [
        ("Chunky-Paper-1.5.66.jar", "Chunky"),
        ("Geyser-Spigot.jar", "Geyser"),
        ("floodgate-spigot.jar", "Floodgate"),
    ]
    for filename, label in candidate_specs:
        path = by_name.get(filename.casefold())
        if path is None:
            continue
        blob = path.read_bytes()
        candidate_hash = hashlib.sha256(blob).hexdigest()
        try:
            with __import__("zipfile").ZipFile(path) as jar:
                bad_member = jar.testzip()
                if bad_member is not None:
                    fail(f"{label} download has a corrupt ZIP member: {bad_member}")
        except Exception as exc:
            fail(f"{label} download is not a valid JAR: {exc}")

        descriptor = a["read_plugin_descriptor"](blob)
        if not descriptor:
            fail(f"{label} download has no readable plugin descriptor.")
        current = next(
            (
                item for item in installed
                if str(item.get("name", "")).casefold().replace("-spigot", "") == label.casefold()
            ),
            None,
        )
        verified, detail = a["official_plugin_candidate"](
            label, path, str(descriptor.get("version", "unknown")), candidate_hash
        )
        if not verified:
            fail(f"{label} candidate is not the latest verified publisher artifact: {detail}")
        if current and current.get("sha256") == candidate_hash:
            continue
        if current:
            comparison = a["compare_versions"](
                str(descriptor.get("version", "unknown")),
                str(current.get("version", "unknown")),
            )
            if comparison == "candidate is older; do not downgrade":
                fail(f"{label} candidate is older than the installed release.")
        old_files = [
            item["file"] for item in installed
            if str(item.get("name", "")).casefold().replace("-spigot", "") == label.casefold()
        ]
        plugin_updates.append({
            "name": label,
            "filename": path.name,
            "version": descriptor.get("version", "unknown"),
            "sha256": candidate_hash,
            "remove_files": old_files,
            "detail": detail,
            "source": str(path),
        })

    desired_keys = set(primary)
    known = set(a["pack_key"](name + ".zip") for name in KNOWN_VANILLA_TWEAKS)
    known.update(desired_keys)
    current_active = {a["pack_key"](name) for name in facts.get("datapacks", [])}
    current_disabled = {
        a["pack_key"](name) for name in facts.get("legacy_disabled_datapacks", [])
    }
    retired = sorted(((current_active | current_disabled) & known) - desired_keys)

    pack_updates = []
    with __import__("zipfile").ZipFile(primary_path) as outer:
        outer_entries = {
            Path(name).name: name
            for name in outer.namelist()
            if name.lower().endswith(".zip") and not name.endswith("/")
        }
        for key, pack in sorted(primary.items()):
            entry = outer_entries.get(pack["filename"])
            if entry is None:
                fail(f"Cannot map datapack back to its bundle entry: {pack['filename']}")
            blob = outer.read(entry)
            digest = hashlib.sha256(blob).hexdigest()
            pack_updates.append({
                "key": key,
                "filename": pack["filename"],
                "sha256": digest,
                "bytes": len(blob),
                "blob": blob,
            })

    datapack_changes = [
        pack for pack in pack_updates
        if facts.get("datapack_hashes", {}).get(pack["filename"]) != pack["sha256"]
    ]

    return {
        "host": host,
        "paper": paper_update,
        "plugins": plugin_updates,
        "datapacks": pack_updates,
        "known_keys": sorted(known),
        "retired_keys": retired,
        "datapack_changes": datapack_changes,
        "paper_current": a["paper_current_version"](facts.get("paper_line", "")),
    }


def make_stage(plan: dict[str, Any]) -> Path:
    stage = Path(tempfile.mkdtemp(prefix="hsmp-addon-stage-"))
    try:
        if plan["paper"]:
            source = Path(plan["paper"]["source"])
            shutil.copy2(source, stage / "server.jar")
        plugin_dir = stage / "plugins"
        for plugin in plan["plugins"]:
            plugin_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(plugin["source"], plugin_dir / plugin["filename"])
        data_dir = stage / "datapacks"
        data_dir.mkdir(parents=True, exist_ok=True)
        for pack in plan["datapacks"]:
            (data_dir / pack["filename"]).write_bytes(pack["blob"])

        manifest = {
            "source_host": plan["host"].lower(),
            "paper": (
                {key: value for key, value in plan["paper"].items() if key != "source"}
                if plan["paper"] else None
            ),
            "plugins": [
                {key: value for key, value in plugin.items() if key != "source"}
                for plugin in plan["plugins"]
            ],
            "datapacks": [
                {key: value for key, value in pack.items() if key != "blob"}
                for pack in plan["datapacks"]
            ],
            "known_vanilla_tweaks_keys": plan["known_keys"],
            "retired_keys": plan["retired_keys"],
        }
        (stage / "update-manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return stage
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def apply_local(
    host: str, server_dir: str, stage: Path, target: str,
    config: tuple[str, ...],
) -> None:
    win_session, _target, _ubuntu_dir, _windows_dir, ubu_session, port, _win_backup, _ubu_backup = config
    session = ubu_session if host == "UBUNTU" else win_session
    if host == "WINDOWS":
        locked_apply_staged_changes(Path(server_dir), stage, "windows", session, port)
        return

    parent = str(Path(server_dir).parent)
    remote_stage = run([
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        target, "mktemp", "-d", "-p", parent, ".hagonoy-addon-stage.XXXXXX",
    ])
    remote_stage = remote_stage.strip()
    if not remote_stage.startswith(parent.rstrip("/") + "/"):
        fail("Ubuntu returned an unexpected staging directory.")
    try:
        run_stream([
            "rsync", "-rlt", "--no-perms", "--no-owner", "--no-group",
            "--info=progress2", "-e", "ssh -T -o BatchMode=yes -o ConnectTimeout=8",
            str(stage) + "/", f"{target}:{remote_stage}/",
        ], timeout=600)

        script = Path(__file__).read_text(encoding="utf-8")
        command = [
            "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            target, "python3", "-", "--remote-apply", server_dir, remote_stage,
            "ubuntu", session, port,
        ]
        run(command, input_text=script, timeout=180)
    finally:
        remote = "rm -rf -- " + shlex.quote(remote_stage)
        subprocess.run([
            "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            target, remote,
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)


def lifecycle(host: str, action: str) -> None:
    script = LIFECYCLE_UBUNTU if host == "UBUNTU" else LIFECYCLE_WINDOWS
    run_stream([str(script), action], timeout=1200)


def restore_archive(
    host: str, server_dir: str, target: str, archive_name: str,
    windows_backup_dir: str, ubuntu_backup_dir: str,
    config: tuple[str, ...], expected_sha256: str,
) -> None:
    win_session, _target, _ubuntu_dir, _windows_dir, ubu_session, port, _win_backup, _ubu_backup = config
    session = ubu_session if host == "UBUNTU" else win_session
    host_key = host.lower()
    if host == "WINDOWS":
        archive = Path(windows_backup_dir) / archive_name
        if not archive.is_file():
            raise RuntimeError(f"Verified Windows rollback archive is missing: {archive}")
        locked_restore_archive_local(
            archive, Path(server_dir), host_key, session, port, expected_sha256
        )
        return

    remote_archive = str(Path(ubuntu_backup_dir) / archive_name)
    command = [
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        target, "python3", "-", "--remote-restore", server_dir, remote_archive,
        host_key, session, port, expected_sha256,
    ]
    run(command, input_text=Path(__file__).read_text(encoding="utf-8"), timeout=2400)


def current_state(a: dict[str, Any], config: tuple[str, ...], host: str) -> str:
    win_session, target, _ubuntu_dir, _windows_dir, ubu_session, port, _win_backup_dir, _ubu_backup_dir = config
    return (
        a["ubuntu_state"](target, ubu_session, port)
        if host == "UBUNTU"
        else a["windows_state"](win_session, port)
    )


def other_state(a: dict[str, Any], config: tuple[str, ...], host: str) -> str:
    win_session, target, _ubuntu_dir, _windows_dir, ubu_session, port, _win_backup_dir, _ubu_backup_dir = config
    return (
        a["windows_state"](win_session, port)
        if host == "UBUNTU"
        else a["ubuntu_state"](target, ubu_session, port)
    )


def run_backup_and_get_archive(windows_backup_dir: str) -> tuple[str, str]:
    plan = subprocess.run(
        [str(BACKUP_SCRIPT), "--plan"],
        text=True, capture_output=True, check=False, timeout=90,
    )
    if plan.returncode:
        fail("Dual-host backup preflight failed:\n" + (plan.stderr or plan.stdout).strip())
    print(plan.stdout, end="" if plan.stdout.endswith("\n") else "\n")
    print("[hagonoy-update] Creating the full pre-update backup and leaving the source stopped...")
    output = stream_backup([str(BACKUP_SCRIPT), "--execute-keep-stopped"])
    match_name = re.findall(r"^Archive:\s+(\S+)$", output, re.MULTILINE)
    match_hash = re.findall(r"^SHA-256:\s+([a-fA-F0-9]{64})$", output, re.MULTILINE)
    if not match_name or not match_hash:
        fail("Backup command did not report a verified archive name and SHA-256.")
    archive_name, expected_hash = match_name[-1], match_hash[-1]
    local_archive = Path(windows_backup_dir) / archive_name
    if not local_archive.is_file():
        fail(f"Windows server-backup copy is missing: {local_archive}")
    actual_hash = sha256_path(local_archive)
    if actual_hash.casefold() != expected_hash.casefold():
        fail("Local pre-update backup SHA-256 differs from the backup report.")
    return archive_name, actual_hash


def update_verify(a: dict[str, Any], plan: dict[str, Any], target: str, server_dir: str) -> None:
    facts = a["remote_facts"](target if plan["host"] == "UBUNTU" else None, server_dir)
    if plan["paper"]:
        current = a["paper_current_version"](facts.get("paper_line", ""))
        expected = (plan["paper"]["minecraft_version"], plan["paper"]["build"])
        if current != expected:
            raise RuntimeError(f"Paper startup version mismatch: expected {expected}, found {current}.")
    installed_plugins = facts.get("plugins", [])
    for plugin in plan["plugins"]:
        installed = next(
            (item for item in installed_plugins if item.get("sha256") == plugin["sha256"]),
            None,
        )
        if installed is None:
            raise RuntimeError(f"{plugin['name']} updated JAR hash was not found after startup.")
    datapack_hashes = facts.get("datapack_hashes", {})
    for pack in plan["datapacks"]:
        if datapack_hashes.get(pack["filename"]) != pack["sha256"]:
            raise RuntimeError(f"Datapack was not present with expected hash after startup: {pack['filename']}")
    installed_keys = {a["pack_key"](name) for name in facts.get("datapacks", [])}
    missing = sorted({p["key"] for p in plan["datapacks"]} - installed_keys)
    if missing:
        raise RuntimeError("Datapack inventory verification missing: " + ", ".join(missing))
    installed_all_keys = installed_keys | {
        a_key for a_key in (a["pack_key"](name) for name in facts.get("legacy_disabled_datapacks", []))
    }
    retired_present = sorted(set(plan["retired_keys"]) & installed_all_keys)
    if retired_present:
        raise RuntimeError("Retired VanillaTweaks packs remain active: " + ", ".join(retired_present))
    errors = facts.get("plugin_errors", [])
    if errors:
        raise RuntimeError("Plugin load errors appeared in the new startup log:\n" + "\n".join(errors))
    print("[hagonoy-update] Paper/plugin/datapack post-start verification passed.")


def _maintenance_signal(signum: int, _frame: Any) -> None:
    name = signal.Signals(signum).name
    raise RuntimeError(f"Received {name}; entering the safe maintenance recovery path.")


def main() -> None:
    signal.signal(signal.SIGINT, _maintenance_signal)
    signal.signal(signal.SIGTERM, _maintenance_signal)

    if len(sys.argv) == 7 and sys.argv[1] == "--remote-apply":
        locked_apply_staged_changes(Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], sys.argv[5], sys.argv[6])
        return
    if len(sys.argv) == 8 and sys.argv[1] == "--remote-restore":
        server_dir = Path(sys.argv[2]).resolve(strict=True)
        archive_path = Path(sys.argv[3]).resolve(strict=True)
        locked_restore_archive_local(archive_path, server_dir, sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7])
        return
    if len(sys.argv) != 2 or sys.argv[1] != "--execute":
        fail("Usage: ./hagonoy update --execute")

    for command in ("rsync", "ssh", "tar", "tmux", "python3"):
        if shutil.which(command) is None:
            fail(f"Missing required command: {command}")

    a = addons_module()
    config = a["config_values"]()
    host, win_state, ubu_state = source_states(a, config)
    win_session, target, ubuntu_dir, windows_dir, ubu_session, port, windows_backup_dir, ubuntu_backup_dir = config
    expected_windows_backup = "/mnt/d/Hagonoy-SMP/server-backup"
    if windows_backup_dir != expected_windows_backup:
        fail(f"Windows backup destination must be {expected_windows_backup}; update config/dual-host.conf first.")
    if not Path(windows_backup_dir).is_dir():
        fail(f"Windows server-backup directory is missing: {windows_backup_dir}")
    server_dir = ubuntu_dir if host == "UBUNTU" else windows_dir
    facts = a["remote_facts"](target if host == "UBUNTU" else None, server_dir)
    plan = build_update_plan(a, host, facts)

    print("========== HSMP SERVER UPDATE PLAN ==========")
    print(f"Authoritative host: {host}")
    print(f"Windows canonical: {win_state}")
    print(f"Ubuntu canonical:  {ubu_state}")
    print(f"Minecraft version: {plan['paper_current'][0] if plan['paper_current'] else 'unknown'}")
    if plan["paper"]:
        print(f"Paper: UPDATE to {plan['paper']['build']} — {plan['paper']['detail']}")
    else:
        print("Paper: no replacement required")
    for plugin in plan["plugins"]:
        print(f"Plugin: UPDATE {plugin['name']} to {plugin['version']} — publisher artifact verified")
    if not plan["plugins"]:
        print("Plugins: no verified replacement required")
    print(f"Datapacks selected: {len(plan['datapacks'])}")
    print("Datapacks to add/update:")
    for pack in plan["datapack_changes"]:
        print(f"  {pack['filename']}")
    print("Already identical:")
    changed_names = {pack["filename"] for pack in plan["datapack_changes"]}
    for pack in plan["datapacks"]:
        if pack["filename"] not in changed_names:
            print(f"  {pack['filename']}")
    print(f"VanillaTweaks retired without per-pack prompts: {', '.join(plan['retired_keys']) or 'none'}")
    if not (plan["paper"] or plan["plugins"] or plan["datapack_changes"] or plan["retired_keys"]):
        print("[hagonoy-update] Paper, plugins and the selected VanillaTweaks datapacks are already current. No backup or server stop is needed.")
        return

    stage = make_stage(plan)
    archive_name = ""
    backup_complete = False
    changes_attempted = False
    try:
        print()
        print("A full, verified pre-update server TAR will be created in both server-backup folders.")
        print("The running authoritative server will be gracefully stopped for the backup and remain stopped during file replacement.")
        print("The updater will start it again and verify Paper, plugins and selected datapacks.")
        if not sys.stdin.isatty():
            fail("Update execution requires an interactive terminal.")
        answer = input("Type APPLY HSMP SERVER UPDATES to proceed: ").strip()
        if answer != "APPLY HSMP SERVER UPDATES":
            print("[hagonoy-update] Cancelled. No backup or server file was changed.")
            return

        archive_name, archive_hash = run_backup_and_get_archive(windows_backup_dir)
        backup_complete = True
        if current_state(a, config, host) != "STOPPED":
            fail("Source server was not confirmed stopped after the backup transaction.")
        secondary_state = other_state(a, config, host)
        if secondary_state != "STOPPED":
            fail(
                "Secondary host is not confirmed stopped after backup "
                f"({secondary_state}); refusing to modify the authoritative copy."
            )

        print()
        print("========== APPLY STAGED SERVER UPDATES ==========")
        changes_attempted = True
        apply_local(host, server_dir, stage, target, config)
        secondary_state = other_state(a, config, host)
        if secondary_state != "STOPPED":
            raise RuntimeError(
                "Secondary host changed state during file replacement "
                f"({secondary_state}); refusing to start the updated source."
            )

        print()
        print("========== START UPDATED SERVER ==========")
        secondary_state = other_state(a, config, host)
        if secondary_state != "STOPPED":
            raise RuntimeError(
                "Secondary host is not confirmed stopped before startup "
                f"({secondary_state}); refusing a dual-server start."
            )
        lifecycle(host, "start")
        if current_state(a, config, host) != "RUNNING":
            raise RuntimeError("Updated server did not reach a confirmed RUNNING state.")
        secondary_state = other_state(a, config, host)
        if secondary_state != "STOPPED":
            lifecycle(host, "stop")
            raise RuntimeError(
                "Secondary host became active during startup; the updated source was stopped "
                "to prevent two canonical servers running simultaneously."
            )
        update_verify(a, plan, target, server_dir)
        if other_state(a, config, host) != "STOPPED":
            raise RuntimeError(
                "Secondary host became active during post-start verification; "
                "the updated source will be stopped and rolled back."
            )

        print()
        print("========== HSMP UPDATE SUCCESS ==========")
        print(f"Source host: {host}")
        print(f"Pre-update backup: {archive_name}")
        print(f"Backup SHA-256: {archive_hash}")
        print(f"Paper updated: {'yes' if plan['paper'] else 'no'}")
        print(f"Plugins updated: {len(plan['plugins'])}")
        print(f"Selected datapacks installed: {len(plan['datapacks'])}")
        print(f"Retired VanillaTweaks packs: {len(plan['retired_keys'])}")
    except Exception as exc:
        print(f"[hagonoy-update] UPDATE FAILED: {exc}", file=sys.stderr)
        if not changes_attempted:
            try:
                state = current_state(a, config, host)
                other = other_state(a, config, host)
                if state == "STOPPED" and other == "STOPPED":
                    print("[hagonoy-update] No server files were changed; restarting the unchanged authoritative server.")
                    lifecycle(host, "start")
                elif state == "STOPPED":
                    print(
                        "[hagonoy-update] The source remains stopped because the secondary host is "
                        f"{other}; refusing a possible split-brain restart. No server files were changed.",
                        file=sys.stderr,
                    )
                else:
                    print("[hagonoy-update] No update files were changed; current host state is retained.")
            except Exception as recovery_error:
                print(f"[hagonoy-update] Could not safely recover pre-update host state: {recovery_error}", file=sys.stderr)
            raise SystemExit(1)

        if backup_complete and archive_name:
            try:
                state = current_state(a, config, host)
                if state == "RUNNING":
                    print("[hagonoy-update] Gracefully stopping the failed updated server before rollback...")
                    lifecycle(host, "stop")
                    state = current_state(a, config, host)
                if state != "STOPPED":
                    print("[hagonoy-update] Server state is uncertain; refusing to restore files while Java may be active.", file=sys.stderr)
                    print(f"[hagonoy-update] Verified rollback archive retained: {archive_name}", file=sys.stderr)
                    raise SystemExit(1)
                print("[hagonoy-update] Restoring the complete pre-update server from server-backup...")
                restore_archive(host, server_dir, target, archive_name, windows_backup_dir, ubuntu_backup_dir, config, archive_hash)
                secondary_state = other_state(a, config, host)
                if secondary_state != "STOPPED":
                    raise RuntimeError(
                        "Original server files were restored, but the secondary host is "
                        f"{secondary_state}; leaving the restored source stopped."
                    )
                lifecycle(host, "start")
                if current_state(a, config, host) != "RUNNING":
                    raise RuntimeError("Original server files restored but previous server did not confirm readiness.")
                if other_state(a, config, host) != "STOPPED":
                    lifecycle(host, "stop")
                    raise RuntimeError("Secondary host became active during rollback startup; restored source stopped to prevent split brain.")
                print("[hagonoy-update] ROLLBACK=SUCCESS. Original server generation restored and running.")
            except Exception as rollback_error:
                print(f"[hagonoy-update] ROLLBACK FAILED: {rollback_error}", file=sys.stderr)
                print(f"[hagonoy-update] Keep the verified backup archive: {archive_name}", file=sys.stderr)
        raise SystemExit(1)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"[hagonoy-update] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
