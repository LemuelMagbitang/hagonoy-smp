#!/usr/bin/env python3
"""Read-only inventory of HSMP server-update-downloads and current installations."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS = Path("/mnt/d/Hagonoy-SMP/server-update-downloads")
PACK_FORMATS = {"26.3": (121, 0)}
PRIMARY_BUNDLE = "VanillaTweaks_d831085_UNZIP_ME.zip"
SECONDARY_BUNDLE = "VanillaTweaks-26.3.zip"
PAPER_RE = re.compile(r"^paper-(\d+\.\d+)-(\d+)\.jar$", re.IGNORECASE)
PLUGIN_KEYS = {
    "chunky": "Chunky",
    "geyser": "Geyser",
    "floodgate": "Floodgate",
}


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


def config_values() -> tuple[str, str]:
    config = ROOT / "config" / "dual-host.conf"
    if not config.is_file():
        fail(f"Missing dual-host configuration: {config}")
    code = (
        'source "$1" || exit 1; '
        'printf "%s\\0" "$UBUNTU_SSH_TARGET" "$UBUNTU_SERVER_DIR"'
    )
    values = run(["bash", "-c", code, "bash", str(config)]).split("\0")
    if len(values) != 2 or any(not value for value in values):
        fail("Dual-host configuration is missing Ubuntu connection details.")
    return values[0], values[1]


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
    entries = [
        name for name in archive.namelist()
        if name == "pack.mcmeta" or name.endswith("/pack.mcmeta")
    ]
    if not entries:
        return False, "pack.mcmeta missing"
    root_first = sorted(entries, key=lambda name: ("/" in name, len(name)))[0]
    try:
        data = json.loads(archive.read(root_first).decode("utf-8"))
        pack = data.get("pack")
        if not isinstance(pack, dict):
            return False, "pack metadata object missing"
        min_format = pack.get("min_format")
        max_format = pack.get("max_format")
        pack_format = pack.get("pack_format")
        if min_format is not None and max_format is not None:
            low = format_pair(min_format)
            high = format_pair(max_format)
            return low <= (121, 0) <= high, f"format range {low}–{high}"
        if isinstance(pack_format, int):
            return pack_format == 121, f"pack_format {pack_format}"
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


def remote_facts(target: str, server_dir: str) -> dict[str, Any]:
    remote_code = r'''
import glob, json, os, re, sys, zipfile
from pathlib import Path

server = Path(sys.argv[1])
def plugin_info(path):
    result = {"file": path.name, "bytes": path.stat().st_size}
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
datapacks = sorted(p.name for p in (server / "world" / "datapacks").glob("*.zip"))
legacy = []
for d in server.glob("datapacks-disabled*"):
    if d.is_dir():
        legacy.extend(sorted(p.name for p in d.glob("*.zip")))
print(json.dumps({
    "paper_line": paper_line,
    "plugins": plugins,
    "datapacks": datapacks,
    "legacy_disabled_datapacks": sorted(set(legacy)),
}))
'''
    return json.loads(run([
        "ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
        target, "python3", "-", server_dir,
    ], input_text=remote_code, timeout=35))


def paper_current_version(line: str) -> tuple[str, int] | None:
    match = re.search(r"This server is running Paper version\s+(\d+\.\d+)-(\d+)", line)
    if not match:
        return None
    return match.group(1), int(match.group(2))


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
        SECONDARY_BUNDLE,
    ]
    print("Expected update files:")
    for name in required:
        print(f"  [{'FOUND' if name.casefold() in by_name else 'MISSING'}] {name}")
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

    target, server_dir = config_values()
    facts = remote_facts(target, server_dir)
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
            status = "already installed"
        else:
            status = "older build; do not downgrade"
        print(f"  Paper download:   Minecraft {candidate_version}, build {candidate_build} — {status}")
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
        candidate = read_plugin_descriptor(path.read_bytes())
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
            print(f"  {label}: installed {old_version}; downloaded {new_version} — {compare_versions(new_version, old_version)}")
        api = candidate.get("api-version")
        print(f"    Plugin API declaration: {api or 'not declared'} (this is not, by itself, proof of compatibility with Minecraft 26.3)")

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
    removed = sorted(
        name for key, name in legacy.items() if key not in primary
    )
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
    print("[hagonoy] The updater will use the UNZIP_ME bundle as the desired set; absent old packs are retired automatically, not prompted one-by-one.")


if __name__ == "__main__":
    main()
