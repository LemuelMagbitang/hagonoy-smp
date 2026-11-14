#!/usr/bin/env python3
"""Unit tests for the pure bidirectional world-border synchronization rules."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "bin" / "hagonoy-world-border.py"
SPEC = importlib.util.spec_from_file_location("hagonoy_world_border", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

OW = module.OVERWORLD
NETHER = module.NETHER


class WorldBorderSyncTests(unittest.TestCase):
    def test_parser_accepts_block_and_blocks_notation(self) -> None:
        for reply in (
            "The world border is currently 20000 blocks wide",
            "The world border is currently 2500 block(s) wide",
            "The world border is currently 1250 block wide",
        ):
            self.assertIsNotNone(module.WIDTH_RE.search(reply), reply)

    def test_initial_baseline_accepts_matching_live_pair(self) -> None:
        current = {OW: 20000.0, NETHER: 2500.0}
        targets, reason, initializing = module.calculate_targets(current, None)
        self.assertEqual(targets, current)
        self.assertTrue(initializing)
        self.assertIn("baseline", reason.lower())

    def test_initial_baseline_rejects_mismatch(self) -> None:
        with self.assertRaises(SystemExit):
            module.calculate_targets({OW: 20000.0, NETHER: 3000.0}, None)

    def test_overworld_change_derives_nether(self) -> None:
        previous = {OW: 20000.0, NETHER: 2500.0}
        current = {OW: 24000.0, NETHER: 2500.0}
        targets, _, initializing = module.calculate_targets(current, previous)
        self.assertFalse(initializing)
        self.assertEqual(targets, {OW: 24000.0, NETHER: 3000.0})

    def test_nether_change_derives_overworld(self) -> None:
        previous = {OW: 20000.0, NETHER: 2500.0}
        current = {OW: 20000.0, NETHER: 3000.0}
        targets, _, _ = module.calculate_targets(current, previous)
        self.assertEqual(targets, {OW: 24000.0, NETHER: 3000.0})

    def test_both_changed_consistently_are_accepted(self) -> None:
        previous = {OW: 20000.0, NETHER: 2500.0}
        current = {OW: 16000.0, NETHER: 2000.0}
        targets, _, _ = module.calculate_targets(current, previous)
        self.assertEqual(targets, current)

    def test_both_changed_inconsistently_are_rejected(self) -> None:
        previous = {OW: 20000.0, NETHER: 2500.0}
        current = {OW: 16000.0, NETHER: 3000.0}
        with self.assertRaises(SystemExit):
            module.calculate_targets(current, previous)

    def test_no_change_requires_saved_pair_to_remain_synchronized(self) -> None:
        previous = {OW: 20000.0, NETHER: 2500.0}
        current = dict(previous)
        targets, _, _ = module.calculate_targets(current, previous)
        self.assertEqual(targets, current)


if __name__ == "__main__":
    unittest.main()
