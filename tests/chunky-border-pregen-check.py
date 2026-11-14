#!/usr/bin/env python3
"""Offline tests for Chunky world-border selection and task reconciliation."""
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "hagonoy_chunky_pregen.py"
SPEC = importlib.util.spec_from_file_location("hagonoy_chunky_pregen", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def test_center_and_radius_output_parsing() -> None:
    center = module.CENTER_RE.search("Center changed to -2349, 38.")
    radius = module.RADIUS_RE.search("Radius changed to 10000.")
    assert center and tuple(map(float, center.groups())) == (-2349.0, 38.0)
    assert radius and float(radius.group(1)) == 10000.0


def test_dimension_specific_selection_fingerprints() -> None:
    overworld = {
        "center_x": -2349.0, "center_z": 38.0,
        "radius_x": 10000.0, "radius_z": 10000.0, "shape": "square",
    }
    nether = {
        "center_x": -293.0, "center_z": 4.0,
        "radius_x": 1250.0, "radius_z": 1250.0, "shape": "square",
    }
    end = {
        "center_x": 0.0, "center_z": 0.0,
        "radius_x": 10000.0, "radius_z": 10000.0, "shape": "square",
    }
    assert module.fingerprint_matches(overworld, dict(overworld))
    assert not module.fingerprint_matches(overworld, nether)
    assert not module.fingerprint_matches(overworld, end)


def test_border_diameter_verification_accepts_and_rejects() -> None:
    selection = {"radius_x": 1250.0}
    module.verify_border_diameter(selection, 2500.0, "world_nether")
    try:
        module.verify_border_diameter(selection, 3000.0, "world_nether")
    except RuntimeError as exc:
        assert "does not match" in str(exc)
    else:
        raise AssertionError("mismatched imported border diameter must fail")


def test_pause_acknowledgement_patterns() -> None:
    assert module.PAUSED_RE.search("Task paused for world_nether.")
    assert module.NO_TASKS_PAUSE_RE.search("No tasks to pause.")


def test_only_full_ring_tasks_match() -> None:
    border = {
        "center_x": -2349.0, "center_z": 38.0,
        "radius_x": 10000.0, "radius_z": 10000.0,
        "shape": "square", "pattern": "ring",
    }
    csv_subset = dict(border, pattern="csv", csv="partial.csv")
    assert module.fingerprint_matches(border, border)
    assert not module.fingerprint_matches(csv_subset, border)


def test_task_properties_preserve_each_world_selection() -> None:
    values = module.properties(
        "world=world_nether\n"
        "cancelled=false\n"
        "center-x=-293\n"
        "center-z=4\n"
        "radius=1250\n"
        "shape=square\n"
    )
    fingerprint = module.task_fingerprint_from_properties(values)
    assert fingerprint is not None
    assert module.fingerprint_matches(fingerprint, {
        "center_x": -293.0, "center_z": 4.0,
        "radius_x": 1250.0, "radius_z": 1250.0, "shape": "square",
    })


def test_task_log_completion_is_matched_to_geometry() -> None:
    log = (
        "[2026-11-14 10:00:00] started world=world center-x=-2349 center-z=38 "
        "radius=10000 shape=square pattern=ring\n"
        "[2026-11-14 10:30:00] completed world=world center-x=-2349 center-z=38 "
        "radius=10000 shape=square pattern=ring chunks=100000 time=0:30:00\n"
        "[2026-11-14 10:31:00] started world=world_nether center-x=-293 center-z=4 "
        "radius=1250 shape=square pattern=ring\n"
    )
    event = module.latest_task_event(log, "world")
    assert event is not None and event[0] == "completed"
    assert module.fingerprint_matches(event[1], {
        "center_x": -2349.0, "center_z": 38.0,
        "radius_x": 10000.0, "radius_z": 10000.0, "shape": "square",
    })
    assert module.latest_task_event(log, "world_the_end") is None


def test_latest_paused_event_overrides_old_completion() -> None:
    log = (
        "[2026-11-14 10:00:00] completed world=world_the_end center-x=0 center-z=0 "
        "radius=10000 shape=square pattern=ring chunks=1 time=0:00:01\n"
        "[2026-11-14 10:01:00] continued world=world_the_end center-x=0 center-z=0 "
        "radius=10000 shape=square pattern=ring\n"
        "[2026-11-14 10:02:00] paused world=world_the_end center-x=0 center-z=0 "
        "radius=10000 shape=square pattern=ring chunks=2 time=0:00:02\n"
    )
    event = module.latest_task_event(log, "world_the_end")
    assert event is not None and event[0] == "paused"


def test_task_paths_are_dimension_specific_and_reject_traversal() -> None:
    assert module.task_paths("world")[0] == "plugins/Chunky/tasks/world.properties"
    assert module.task_paths("world_nether")[0] == "plugins/Chunky/tasks/world_nether.properties"
    assert module.task_paths("minecraft:the_end")[0] == "plugins/Chunky/tasks/minecraft/the_end.properties"
    try:
        module.task_paths("../escape")
    except RuntimeError:
        pass
    else:
        raise AssertionError("path traversal should be rejected")


def test_atomic_runtime_state_save_and_reload() -> None:
    import tempfile

    previous = module.STATE
    with tempfile.TemporaryDirectory(prefix="chunky-border-state-test-") as tmp:
        module.STATE = Path(tmp) / "state.json"
        state = {"schema": 1, "worlds": {"world": {
            "center_x": -2349, "center_z": 38, "radius_x": 10000,
            "radius_z": 10000, "shape": "square", "status": "running",
        }}}
        module.save_pregen_state(state)
        loaded = module.load_pregen_state()
        assert loaded == state
    module.STATE = previous


def test_external_active_task_requires_matching_selection() -> None:
    previous = module.task_snapshot
    desired = {
        "center_x": -293.0, "center_z": 4.0,
        "radius_x": 1250.0, "radius_z": 1250.0, "shape": "square",
    }
    try:
        module.task_snapshot = lambda *args: ({
            "center-x": "-293", "center-z": "4", "radius": "1250",
            "shape": "square",
        }, None)
        assert module.active_task_matches("UBUNTU", "host", "server", "world_nether", desired)
        module.task_snapshot = lambda *args: ({
            "center-x": "-293", "center-z": "4", "radius": "900",
            "shape": "square",
        }, None)
        assert not module.active_task_matches("UBUNTU", "host", "server", "world_nether", desired)
    finally:
        module.task_snapshot = previous


def test_only_square_chunky_selection_is_accepted() -> None:
    expected = {
        "center_x": 0, "center_z": 0, "radius_x": 10000,
        "radius_z": 10000, "shape": "square",
    }
    assert module.fingerprint_matches(expected, expected)
    expected["shape"] = "circle"
    assert not module.fingerprint_matches(expected, {
        "center_x": 0, "center_z": 0, "radius_x": 10000,
        "radius_z": 10000, "shape": "square",
    })


if __name__ == "__main__":
    for test in (
        test_center_and_radius_output_parsing,
        test_dimension_specific_selection_fingerprints,
        test_border_diameter_verification_accepts_and_rejects,
        test_only_full_ring_tasks_match,
        test_pause_acknowledgement_patterns,
        test_task_properties_preserve_each_world_selection,
        test_task_log_completion_is_matched_to_geometry,
        test_latest_paused_event_overrides_old_completion,
        test_task_paths_are_dimension_specific_and_reject_traversal,
        test_only_square_chunky_selection_is_accepted,
        test_atomic_runtime_state_save_and_reload,
        test_external_active_task_requires_matching_selection,
    ):
        test()
    print("[DONE] Chunky border pre-generation tests passed.")
