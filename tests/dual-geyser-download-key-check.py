#!/usr/bin/env python3
"""Regression test: GeyserMC download URLs use the API download key, not file name."""
from __future__ import annotations

import ast
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "bin" / "hagonoy-generation"


def fail(message: str) -> None:
    raise RuntimeError(message)


def run_case(project: str, version: str, build: int, expected_name: str) -> None:
    source_text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(source_text, filename=str(SOURCE))
    function = next(
        (node for node in tree.body
         if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
         and node.name == "fetch_geysermc_default_build"),
        None,
    )
    if function is None:
        raise AssertionError("fetch_geysermc_default_build() not found")

    checksum = "a" * 64
    calls: list[tuple[str, str, str]] = []

    def fake_api(url: str, user_agent: str) -> dict:
        calls.append(("api", url, user_agent))
        return {"version": version}

    def fake_builds(selected_project: str, selected_version: str, user_agent: str) -> list[dict]:
        assert selected_project == project
        assert selected_version == version
        calls.append(("builds", selected_project, selected_version))
        # Contract: fetch_geysermc_default_builds() returns default-channel
        # builds only. Experimental-channel filtering is covered by the core
        # API regression suite, which exercises the real filtering function.
        return [
            {
                "build": build,
                "channel": "default",
                "time": "2026-11-12T00:00:00Z",
                "downloads": {
                    "spigot": {"name": expected_name, "sha256": checksum}
                },
            },
        ]

    namespace = {
        "urllib": urllib,
        "re": re,
        "fail": fail,
        "geysermc_api_json": fake_api,
        "fetch_geysermc_default_builds": fake_builds,
    }
    module = ast.Module(body=[function], type_ignores=[])
    exec(compile(module, str(SOURCE), "exec"), namespace)
    metadata = namespace["fetch_geysermc_default_build"](project, "HSMP-test/1.0")

    expected_url = (
        f"https://download.geysermc.org/v2/projects/{project}/versions/"
        f"{version}/builds/{build}/downloads/spigot"
    )
    assert metadata["url"] == expected_url, (
        f"wrong download URL: {metadata['url']!r}; expected {expected_url!r}"
    )
    assert metadata["name"] == expected_name
    assert metadata["platform"] == "spigot"
    assert metadata["sha256"] == checksum
    assert metadata["build"] == build
    assert metadata["channel"] == "default"
    assert not metadata["url"].endswith(expected_name)

    print(f"[OK] {project} build {build} URL uses /downloads/spigot, not {expected_name}.")


def main() -> int:
    if not SOURCE.is_file():
        print(f"[ERROR] Source file not found: {SOURCE}", file=sys.stderr)
        return 2
    run_case("geyser", "2.12.1", 1302, "Geyser-Spigot.jar")
    run_case("floodgate", "2.2.5", 141, "floodgate-spigot.jar")
    print("[DONE] GeyserMC download-key regression checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
