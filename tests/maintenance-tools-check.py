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
assert border["WIDTH_RE"].search("World border is currently 10000 block(s) wide")

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

with tempfile.TemporaryDirectory(prefix="hsmp-addon-test-") as tmp:
    bundle = Path(tmp) / "VanillaTweaks_d831085_UNZIP_ME.zip"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as outer:
        outer.writestr("painting picker v1.1.5 (MC 26.3).zip", make_pack(121))
        outer.writestr("old pack v1.0 (MC old).zip", make_pack(120))
    packs = addons["read_bundle"](bundle)
    assert packs["painting picker"]["compatible"] is True
    assert packs["old pack"]["compatible"] is False

print("[OK] World-border targets and no-shrink policy constants")
print("[OK] Version comparison and VanillaTweaks filename reconciliation")
print("[OK] Nested datapack ZIP and 26.3 pack-format inspection")
