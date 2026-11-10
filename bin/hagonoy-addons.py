#!/usr/bin/env python3
"""Read-only inventory of HSMP server-update-downloads and current installations."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path("/mnt/d/Hagonoy-SMP/server-update-downloads")
TARGET_DATA_PACK_FORMAT = (121, 0)
PRIMARY_BUNDLE = "VanillaTweaks_d831085_UNZIP_ME.zip"
SECONDARY_BUNDLE = "VanillaTweaks-26.3.zip"
PAPER_RE = re.compile(r"^paper-(\d+\.\d+)-(\d+)\.jar$", re.IGNORECASE)
def fail(message: str) -> "NoReturn":
    print(f"[hagonoy] ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def run(args: list[str], *, input_text: str | None = None, timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            args, input=input_text, text=True, capture_output=True,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        fail(f"Could not run {args[0]}: {exc}")
    if result.returncode:
        fail(f"{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def config_values() -> tuple[str, str, str, str, str, str]:
    config = ROOT / "config" / "dual-host.conf"
    if not config.is_file():
        fail(f"Missing dual-host configuration: {config}")
    code = (
        'source "$1" || exit 1; '
        'printf "%s\\0" "$WINDOWS_TMUX_SESSION" "$UBUNTU_SSH_TARGET" '
        '"$UBUNTU_SERVER_DIR" "$WINDOWS_SERVER_DIR" "$UBUNTU_TMUX_SESSION" "$MINECRAFT_PORT"'
    )
    values = run(["bash", "-c", code, "bash", str(config)]).rstrip("\0").split("\0")
    if len(values) != 6 or any(not value for value in values):
        fail("Dual-host configuration is missing server or connection details.")
    return tuple(values)


def read_plugin_descriptor(blob: bytes) -> dict[str, str]:
    try:
        with zipfile.ZipFile(__import__("io").BytesIO(blob)) as jar:
            names = set(jar.namelist())
            descriptor = next(
                (name for name in ("paper-plugin.yml", "plugin.yml") if name in names),
                None,
            )
            if descriptor is None:
                return {}
            text = jar.read(descriptor).decode("utf-8", errors="replace")
    except (OSError, zipfile.BadZipFile):
        return {}
    result: dict[str, str] = {}
    for key in ("name", "version", "api-version", "main"):
        match = re.search(
            rf"(?m)^{re.escape(key)}\s*:\s*['\"]?([^#\r\n'\"]+)['\"]?\s*$",
            text,
        )
        if match:
            result[key] = match.group(1).strip()
    return result


def version_tuple(value: str) -> tuple[int, ...] | None:
    match = re.match(r"^\s*(\d+(?:\.\d+){0,4})", value)
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def compare_versions(candidate: str, installed: str) -> str:
    new = version_tuple(candidate)
    old = version_tuple(installed)
    if new is None or old is None:
        return "different/unparsed release labels; verify release notes"
    width = max(len(new), len(old))
    new += (0,) * (width - len(new))
    old += (0,) * (width - len(old))
    if new > old:
        return "candidate is newer"
    if new == old:
        return "same version"
    return "candidate is older; do not downgrade"


def pack_key(filename: str) -> str:
    stem = Path(filename).stem
    return re.sub(r"\s+v\d.*$", "", stem, flags=re.IGNORECASE).strip().casefold()


def pack_metadata(archive: zipfile.ZipFile) -> tuple[bool, str]:
    names = archive.namelist()
    if "pack.mcmeta" not in names:
        if any(name.endswith("/pack.mcmeta") for name in names):
            return False, "pack.mcmeta is nested below the ZIP root"
        return False, "top-level pack.mcmeta missing"
    try:
        bad_member = archive.testzip()
        if bad_member is not None:
            return False, f"corrupt ZIP member: {bad_member}"
        data = json.loads(archive.read("pack.mcmeta").decode("utf-8"))
        pack = data.get("pack")
        if not isinstance(pack, dict):
            return False, "pack metadata object missing"
        min_format = pack.get("min_format")
        max_format = pack.get("max_format")
        pack_format = pack.get("pack_format")
        if min_format is not None and max_format is not None:
            low = format_pair(min_format)
            high = format_pair(max_format)
            return low <= TARGET_DATA_PACK_FORMAT <= high, f"format range {low}–{high}"
        if isinstance(pack_format, int):
            return pack_format == TARGET_DATA_PACK_FORMAT[0], f"pack_format {pack_format}"
        return False, "no recognized format range for 26.3"
    except Exception as exc:
        return False, f"invalid pack.mcmeta: {exc}"


def format_pair(value: Any) -> tuple[int, int]:
    if isinstance(value, int):
        return value, 0
    if (
        isinstance(value, list) and len(value) in (1, 2)
        and all(isinstance(item, int) and not isinstance(item, bool) for item in value)
    ):
        return value[0], value[1] if len(value) == 2 else 0
    raise ValueError(f"unsupported format value: {value!r}")


def read_bundle(path: Path) -> dict[str, dict[str, Any]]:
    packs: dict[str, dict[str, Any]] = {}
    if not path.is_file():
        return packs
    try:
        with zipfile.ZipFile(path) as outer:
            for name in sorted(outer.namelist()):
                if not name.lower().endswith(".zip") or name.endswith("/"):
                    continue
                blob = outer.read(name)
                with zipfile.ZipFile(__import__("io").BytesIO(blob)) as inner:
                    compatible, details = pack_metadata(inner)
                filename = Path(name).name
                key = pack_key(filename)
                packs[key] = {
                    "filename": filename,
                    "compatible": compatible,
                    "details": details,
                    "bytes": len(blob),
                }
    except (OSError, zipfile.BadZipFile) as exc:
        fail(f"Cannot inspect VanillaTweaks bundle {path.name}: {exc}")
    return packs


def remote_facts(target: str | None, server_dir: str) -> dict[str, Any]:
    remote_code = r'''
import glob, hashlib, json, os, re, sys, zipfile
from pathlib import Path

server = Path(sys.argv[1])
def plugin_info(path):
    result = {"file": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    try:
        with zipfile.ZipFile(path) as jar:
            names = set(jar.namelist())
            desc = next((n for n in ("paper-plugin.yml", "plugin.yml") if n in names), None)
            if desc:
                text = jar.read(desc).decode("utf-8", "replace")
                for key in ("name", "version", "api-version", "main"):
                    m = re.search(r"(?m)^" + re.escape(key) + r"\s*:\s*['\"]?([^#\r\n'\"]+)['\"]?\s*$", text)
                    if m: result[key] = m.group(1).strip()
    except Exception as exc:
        result["error"] = str(exc)
    return result

log = server / "logs" / "latest.log"
paper_line = ""
if log.is_file():
    for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
        if "This server is running Paper version " in line:
            paper_line = line
plugins = [plugin_info(Path(p)) for p in sorted(glob.glob(str(server / "plugins" / "*.jar")))]
paper_jar = server / "server.jar"
paper_jar_info = None
if paper_jar.is_file():
    paper_jar_info = {
        "file": paper_jar.name,
        "bytes": paper_jar.stat().st_size,
        "sha256": hashlib.sha256(paper_jar.read_bytes()).hexdigest(),
    }
datapacks = sorted(p.name for p in (server / "world" / "datapacks").glob("*.zip"))
legacy = []
for d in server.glob("datapacks-disabled*"):
    if d.is_dir():
        legacy.extend(sorted(p.name for p in d.glob("*.zip")))
print(json.dumps({
    "paper_line": paper_line,
    "paper_jar": paper_jar_info,
    "plugins": plugins,
    "datapacks": datapacks,
    "legacy_disabled_datapacks": sorted(set(legacy)),
}))
'''
    if target:
        output = run([
            "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
            target, "python3", "-", server_dir,
        ], input_text=remote_code, timeout=35)
    else:
        output = run(["python3", "-", server_dir], input_text=remote_code, timeout=35)
    return json.loads(output)


def windows_state(session: str, port: str) -> str:
    session_running = subprocess.run(
        ["tmux", "has-session", "-t", f"={session}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    command = (
        f"$c=Get-NetTCPConnection -State Listen -LocalPort {int(port)} "
        "-ErrorAction SilentlyContinue; if ($c) {'LISTENING'} else {'STOPPED'}"
    )
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
            text=True, capture_output=True, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    port_state = result.stdout.strip().replace("\r", "") if result.returncode == 0 else "UNKNOWN"
    if session_running and port_state == "LISTENING":
        return "RUNNING"
    if not session_running and port_state == "STOPPED":
        return "STOPPED"
    return "UNKNOWN"


def ubuntu_state(target: str, session: str, port: str) -> str:
    code = (
        f"if tmux has-session -t '={session}' 2>/dev/null && "
        f"ss -H -ltn 'sport = :{int(port)}' 2>/dev/null | grep -q .; then "
        "echo RUNNING; "
        f"elif ! tmux has-session -t '={session}' 2>/dev/null && "
        f"! ss -H -ltn 'sport = :{int(port)}' 2>/dev/null | grep -q .; then "
        "echo STOPPED; else echo UNKNOWN; fi"
    )
    try:
        result = subprocess.run(
            ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", target, code],
            text=True, capture_output=True, timeout=15, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "UNKNOWN"
    if result.returncode:
        return "UNKNOWN"
    value = result.stdout.strip()
    return value if value in {"RUNNING", "STOPPED"} else "UNKNOWN"


def paper_current_version(line: str) -> tuple[str, int] | None:
    match = re.search(r"This server is running Paper version\s+(\d+\.\d+)-(\d+)", line)
    if not match:
        return None
    return match.group(1), int(match.group(2))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def official_paper_candidate(path: Path, minecraft_version: str, build: int) -> tuple[bool, str]:
    api_url = f"https://fill.papermc.io/v3/projects/paper/versions/{minecraft_version}/builds"
    request = urllib.request.Request(
        api_url,
        headers={"User-Agent": "HagonoySMPManager/1.0 (https://github.com/LemuelMagbitang/hagonoy-smp)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"PaperMC API verification unavailable: {exc}"
    if not isinstance(payload, list):
        return False, "PaperMC returned an unexpected builds response"
    stable = [
        item for item in payload
        if isinstance(item, dict) and item.get("channel") == "STABLE"
        and isinstance(item.get("id"), int)
    ]
    if not stable:
        return False, f"PaperMC has no stable build for Minecraft {minecraft_version}"
    latest = stable[0]
    latest_build = latest["id"]
    if build != latest_build:
        return False, f"downloaded build {build}; latest stable is {latest_build}"
    download = latest.get("downloads", {}).get("server:default", {})
    expected_size = download.get("size")
    expected_hash = download.get("checksums", {}).get("sha256")
    if not isinstance(expected_size, int) or not isinstance(expected_hash, str):
        return False, "PaperMC response lacks expected size or SHA-256 metadata"
    if path.stat().st_size != expected_size:
        return False, f"file size mismatch (expected {expected_size:,}, found {path.stat().st_size:,})"
    actual_hash = sha256_file(path)
    if actual_hash.casefold() != expected_hash.casefold():
        return False, f"SHA-256 mismatch (expected {expected_hash}, found {actual_hash})"
    try:
        with zipfile.ZipFile(path) as jar:
            bad = jar.testzip()
            if bad is not None or "META-INF/MANIFEST.MF" not in jar.namelist():
                return False, f"invalid Paper JAR archive ({bad or 'manifest missing'})"
    except (OSError, zipfile.BadZipFile) as exc:
        return False, f"invalid Paper JAR: {exc}"
    return True, f"official stable build {latest_build}; size and SHA-256 verified"


def fetch_json(url: str) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HagonoySMPManager/1.0 (https://github.com/LemuelMagbitang/hagonoy-smp)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def official_chunky_candidate(path: Path, candidate_version: str, candidate_hash: str) -> tuple[bool, str]:
    url = (
        "https://api.modrinth.com/v2/project/chunky/version"
        "?game_versions=%5B%2226.3%22%5D&loaders=%5B%22paper%22%5D"
    )
    try:
        versions = fetch_json(url)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"Modrinth compatibility metadata unavailable: {exc}"
    if not isinstance(versions, list) or not versions:
        return False, "Modrinth returned no Paper releases for Minecraft 26.3"
    releases = [
        item for item in versions
        if isinstance(item, dict) and item.get("version_type") == "release"
    ]
    if not releases:
        return False, "No stable Chunky release for Paper/Minecraft 26.3 was found"
    releases.sort(key=lambda item: str(item.get("date_published", "")), reverse=True)
    latest = releases[0]
    files = latest.get("files", [])
    artifact = next(
        (item for item in files if item.get("filename") == path.name),
        None,
    )
    if artifact is None:
        return False, f"latest compatible Chunky release is {latest.get('version_number', 'unknown')}; it does not publish {path.name}"
    expected_hash = artifact.get("hashes", {}).get("sha256")
    if not isinstance(expected_hash, str):
        return False, "Modrinth did not publish a SHA-256 for the Paper artifact"
    if candidate_version != str(latest.get("version_number", "")):
        return False, f"candidate version {candidate_version}; latest compatible release is {latest.get('version_number')}"
    if candidate_hash.casefold() != expected_hash.casefold():
        return False, "Chunky JAR SHA-256 does not match the latest compatible Modrinth artifact"
    return True, f"official Modrinth release {candidate_version}; Paper + Minecraft 26.3 compatibility and SHA-256 verified"


def official_geysermc_candidate(project: str, path: Path, candidate_hash: str) -> tuple[bool, str]:
    url = f"https://download.geysermc.org/v2/projects/{project}/versions/latest/builds"
    try:
        payload = fetch_json(url)
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return False, f"GeyserMC build metadata unavailable: {exc}"
    if not isinstance(payload, dict) or not isinstance(payload.get("builds"), list):
        return False, "GeyserMC returned an unexpected builds response"
    builds = [
        item for item in payload["builds"]
        if isinstance(item, dict) and item.get("channel") == "default"
        and isinstance(item.get("build"), int)
    ]
    promoted = [item for item in builds if item.get("promoted") is True]
    candidates = promoted or builds
    if not candidates:
        return False, "GeyserMC has no default Spigot/Paper build metadata"
    latest = max(candidates, key=lambda item: item["build"])
    artifact = latest.get("downloads", {}).get("spigot", {})
    if artifact.get("name") != path.name:
        return False, f"latest {project} build {latest['build']} does not publish {path.name}"
    expected_hash = artifact.get("sha256")
    if not isinstance(expected_hash, str):
        return False, "GeyserMC did not publish a SHA-256 for the Spigot/Paper artifact"
    detail = f"GeyserMC {payload.get('version', 'latest')} build {latest['build']}"
    if candidate_hash.casefold() != expected_hash.casefold():
        return False, f"{detail}; downloaded JAR SHA-256 does not match publisher artifact"
    return True, f"{detail}; official Spigot/Paper SHA-256 verified"


def official_plugin_candidate(label: str, path: Path, candidate_version: str, candidate_hash: str) -> tuple[bool, str]:
    if label == "Chunky":
        return official_chunky_candidate(path, candidate_version, candidate_hash)
    if label == "Geyser":
        return official_geysermc_candidate("geyser", path, candidate_hash)
    if label == "Floodgate":
        return official_geysermc_candidate("floodgate", path, candidate_hash)
    return False, "no publisher metadata adapter for this plugin"


def print_download_inventory(files: list[Path]) -> None:
    print(f"Download directory: {DOWNLOADS}")
    print("Files available:")
    for path in files:
        size = path.stat().st_size
        print(f"  {path.name}  ({size:,} bytes)")
    print()


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] != "--plan":
        fail("Usage: ./hagonoy addons --plan")

    if not DOWNLOADS.is_dir():
        fail(f"Download directory does not exist: {DOWNLOADS}")
    files = sorted(path for path in DOWNLOADS.iterdir() if path.is_file())
    print("========== HSMP ADDON / UPDATE INVENTORY ==========")
    print_download_inventory(files)

    by_name = {path.name.casefold(): path for path in files}
    required = [
        "paper-26.3-244.jar",
        "Chunky-Paper-1.5.66.jar",
        "Geyser-Spigot.jar",
        "floodgate-spigot.jar",
        PRIMARY_BUNDLE,
    ]
    print("Expected update files:")
    for name in required:
        print(f"  [{'FOUND' if name.casefold() in by_name else 'MISSING'}] {name}")
    optional_status = "FOUND" if SECONDARY_BUNDLE.casefold() in by_name else "not present (optional)"
    print(f"Optional comparison-only archive: [{optional_status}] {SECONDARY_BUNDLE}")
    print()

    primary_path = by_name.get(PRIMARY_BUNDLE.casefold())
    secondary_path = by_name.get(SECONDARY_BUNDLE.casefold())
    if primary_path is None:
        fail(f"Selected VanillaTweaks source is missing: {PRIMARY_BUNDLE}")
    primary = read_bundle(primary_path)
    secondary = read_bundle(secondary_path) if secondary_path else {}

    if not primary:
        fail(f"No individual datapack ZIPs were found inside {PRIMARY_BUNDLE}.")

    print(f"Selected VanillaTweaks source: {PRIMARY_BUNDLE}")
    print("This UNZIP_ME bundle is treated as the authoritative selected datapack set.")
    print("Nested datapack ZIPs:")
    blocked = []
    for pack in sorted(primary.values(), key=lambda p: p["filename"].casefold()):
        status = "READY" if pack["compatible"] else "CHECK"
        print(f"  [{status}] {pack['filename']} — {pack['details']}")
        if not pack["compatible"]:
            blocked.append(pack["filename"])

    if secondary:
        selected = set(primary)
        other = set(secondary)
        only_secondary = sorted(
            secondary[key]["filename"] for key in other - selected
        )
        only_primary = sorted(
            primary[key]["filename"] for key in selected - other
        )
        print()
        print(f"Secondary bundle: {SECONDARY_BUNDLE} (inventory only; not the selected set)")
        print(f"  Present only in UNZIP_ME: {', '.join(only_primary) or 'none'}")
        print(f"  Present only in secondary ZIP: {', '.join(only_secondary) or 'none'}")
        print("The updater will not union these bundles; this prevents re-adding packs absent from your UNZIP_ME selection.")

    win_session, target, ubuntu_dir, windows_dir, ubu_session, port = config_values()
    win_state = windows_state(win_session, port)
    ubu_state = ubuntu_state(target, ubu_session, port)
    print(f"Windows canonical: {win_state}")
    print(f"Ubuntu canonical:  {ubu_state}")
    if win_state == "UNKNOWN" or ubu_state == "UNKNOWN":
        fail("A canonical host state is uncertain; cannot determine which installed server is authoritative.")
    if win_state == "RUNNING" and ubu_state == "RUNNING":
        fail("Both canonical servers appear to be running; resolve this before update planning.")
    if win_state == "STOPPED" and ubu_state == "STOPPED":
        fail("Both canonical servers are stopped; no authoritative installed server can be selected.")
    if ubu_state == "RUNNING":
        source_host, facts = "UBUNTU", remote_facts(target, ubuntu_dir)
    else:
        source_host, facts = "WINDOWS", remote_facts(None, windows_dir)
    print(f"Installed source: {source_host}")
    current_paper = paper_current_version(facts.get("paper_line", ""))
    paper_candidate_path = next(
        (p for p in files if PAPER_RE.match(p.name)), None
    )
    print()
    print("Installed server and plugin comparison:")
    if current_paper:
        print(f"  Paper installed: Minecraft {current_paper[0]}, build {current_paper[1]}")
    else:
        print("  Paper installed: version could not be parsed from logs/latest.log")
    if paper_candidate_path:
        match = PAPER_RE.match(paper_candidate_path.name)
        assert match is not None
        candidate_version, candidate_build = match.group(1), int(match.group(2))
        if current_paper is None:
            status = "cannot compare"
        elif candidate_version != current_paper[0]:
            status = "different Minecraft version; separate world-upgrade review required"
        elif candidate_build > current_paper[1]:
            status = "newer build candidate"
        elif candidate_build == current_paper[1]:
            status = "same build"
        else:
            status = "older build; do not downgrade"
        print(f"  Paper download:   Minecraft {candidate_version}, build {candidate_build} — {status}")
        if current_paper and candidate_version == current_paper[0]:
            verified, detail = official_paper_candidate(paper_candidate_path, candidate_version, candidate_build)
            print(f"  Paper authenticity: {'VERIFIED' if verified else 'BLOCKED'} — {detail}")
        else:
            print("  Paper authenticity: BLOCKED — Minecraft version cannot be safely matched.")
        current_jar = facts.get("paper_jar")
        candidate_hash = sha256_file(paper_candidate_path)
        if current_jar:
            print(f"  Installed JAR:    {current_jar['file']} ({current_jar['bytes']:,} bytes, SHA-256 {current_jar['sha256']})")
            print(f"  Download SHA-256: {candidate_hash}")
            if candidate_hash == current_jar["sha256"]:
                print("  Paper file state: exact same binary; no replacement needed")
            elif current_paper and candidate_version == current_paper[0] and candidate_build == current_paper[1]:
                print("  Paper file state: same reported build, different binary; do not replace automatically")
        else:
            print("  Installed JAR:    server.jar was not found for hash comparison")
    else:
        print("  Paper download:   no recognizable paper-<mc>-<build>.jar candidate found")

    installed = facts.get("plugins", [])
    candidates = [
        ("Chunky-Paper-1.5.66.jar", "Chunky"),
        ("Geyser-Spigot.jar", "Geyser"),
        ("floodgate-spigot.jar", "Floodgate"),
    ]
    for filename, label in candidates:
        path = by_name.get(filename.casefold())
        if path is None:
            print(f"  {label}: download missing")
            continue
        candidate_blob = path.read_bytes()
        candidate_hash = hashlib.sha256(candidate_blob).hexdigest()
        try:
            with zipfile.ZipFile(path) as jar:
                corrupt = jar.testzip()
                if corrupt is not None:
                    raise ValueError(f"corrupt JAR member: {corrupt}")
        except (OSError, zipfile.BadZipFile, ValueError) as exc:
            print(f"  {label}: downloaded JAR integrity check failed: {exc}")
            continue
        candidate = read_plugin_descriptor(candidate_blob)
        current = next(
            (item for item in installed
             if str(item.get("name", "")).casefold().replace("-spigot", "") == label.casefold()),
            None,
        )
        if not candidate:
            print(f"  {label}: downloaded JAR has no readable plugin descriptor; update blocked")
            continue
        if current is None:
            print(f"  {label}: {candidate.get('version', 'unknown')} found; plugin not detected as installed")
        else:
            old_version = str(current.get("version", "unknown"))
            new_version = str(candidate.get("version", "unknown"))
            verdict = compare_versions(new_version, old_version)
            if candidate_hash == current.get("sha256"):
                verdict = "identical SHA-256; no update needed"
            elif verdict == "same version":
                verdict = "same version but different binary; hold for manual review"
            print(f"  {label}: installed {old_version}; downloaded {new_version} — {verdict}")
            print(f"    Installed JAR: {current.get('file')} ({current.get('bytes', 0):,} bytes)")
            print(f"    Download SHA-256: {candidate_hash}")
        api = candidate.get("api-version")
        print(f"    Plugin API declaration: {api or 'not declared'}")
        verified, detail = official_plugin_candidate(
            label, path, str(candidate.get("version", "unknown")), candidate_hash
        )
        print(f"    Publisher compatibility: {'VERIFIED' if verified else 'NOT VERIFIED'} — {detail}")

    print()
    print("Datapack reconciliation:")
    active = {pack_key(name): name for name in facts.get("datapacks", [])}
    legacy = {pack_key(name): name for name in facts.get("legacy_disabled_datapacks", [])}
    for key, pack in sorted(primary.items()):
        if key in active:
            print(f"  UPDATE: {active[key]} -> {pack['filename']}")
        elif key in legacy:
            print(f"  REPLACE DISABLED COPY: {legacy[key]} -> active {pack['filename']}")
        else:
            print(f"  ADD: {pack['filename']}")
    retired: dict[str, str] = {}
    for previous in (active, legacy):
        for key, name in previous.items():
            if key not in primary:
                retired[key] = name
    removed = sorted(retired.values(), key=str.casefold)
    if removed:
        print("  RETIRED from your new selection (no prompt; archived in the pre-update backup):")
        for name in removed:
            print(f"    REMOVE OLD COPY: {name}")
    print()
    if blocked:
        print("BLOCKED: one or more datapacks do not declare compatibility with data-pack format 121.0.")
        print("No deployment should proceed until those pack files are corrected or replaced.")
    else:
        print("All selected datapacks declare compatibility with Minecraft 26.3 data-pack format 121.0.")
    print()
    print("[hagonoy] INVENTORY ONLY. No download, server file, plugin, datapack, or world data was changed.")
    print("[hagonoy] The updater will use the UNZIP_ME bundle as the desired set; old active and disabled ZIPs absent from it are retired automatically, not prompted one-by-one.")


if __name__ == "__main__":
    main()
