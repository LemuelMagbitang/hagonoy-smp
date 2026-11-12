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

helper = Path(sys.argv[1])
loader = importlib.machinery.SourceFileLoader("hagonoy_generation_paper_api", str(helper))
spec = importlib.util.spec_from_loader(loader.name, loader)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
loader.exec_module(module)

jar_bytes = b"fixture paper jar bytes - not a real server jar"
sha = hashlib.sha256(jar_bytes).hexdigest()

payload = [
    {"id": 90, "channel": "EXPERIMENTAL"},
    {
        "id": 62,
        "channel": "STABLE",
        "downloads": {
            "server:default": {
                "name": "paper-26.1.2-62.jar",
                "url": "https://fill-data.papermc.io/v1/objects/example/paper.jar",
                "checksums": {"sha256": sha},
                "size": len(jar_bytes)
            }
        }
    },
    {"id": 61, "channel": "STABLE"}
]

user_agent = "HagonoySMPManager/1.0 (https://github.com/LemuelMagbitang/hagonoy-smp)"

print("========== 1. SELECT LATEST STABLE BUILD ==========")
with patch.object(
    module.urllib.request,
    "urlopen",
    return_value=io.BytesIO(json.dumps(payload).encode())
):
    metadata = module.fetch_paper_stable_build("26.1.2", user_agent)

assert metadata["build"] == 62
assert metadata["sha256"] == sha
assert metadata["size"] == len(jar_bytes)
print("[OK] Experimental builds ignored; stable build selected.")

print()
print("========== 2. DOWNLOAD AND SHA-256 VERIFICATION ==========")
with tempfile.TemporaryDirectory() as temporary:
    destination = Path(temporary) / "paper-staged.jar"

    with patch.object(
        module.urllib.request,
        "urlopen",
        return_value=io.BytesIO(jar_bytes)
    ):
        module.download_verified_paper_build(
            metadata, destination, user_agent
        )

    assert destination.read_bytes() == jar_bytes
    print("[OK] Download byte count and SHA-256 verified.")

print()
print("========== 3. CHECKSUM MISMATCH REJECTED ==========")
with tempfile.TemporaryDirectory() as temporary:
    destination = Path(temporary) / "paper-staged.jar"
    bad_metadata = dict(metadata)
    bad_metadata["sha256"] = "0" * 64

    with patch.object(
        module.urllib.request,
        "urlopen",
        return_value=io.BytesIO(jar_bytes)
    ):
        try:
            module.download_verified_paper_build(
                bad_metadata, destination, user_agent
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Checksum mismatch was accepted.")

    assert not destination.exists()
    print("[OK] Invalid JAR deleted and checksum mismatch rejected.")

print()
print("========== 4. NO STABLE BUILD REJECTED ==========")
with patch.object(
    module.urllib.request,
    "urlopen",
    return_value=io.BytesIO(
        json.dumps([{"id": 63, "channel": "EXPERIMENTAL"}]).encode()
    )
):
    try:
        module.fetch_paper_stable_build("26.1.2", user_agent)
    except RuntimeError:
        pass
    else:
        raise AssertionError("Missing stable build was accepted.")

print("[OK] No-stable-build response rejected.")

print()
print("========== ALL PAPER API TESTS PASSED ==========")
PY
