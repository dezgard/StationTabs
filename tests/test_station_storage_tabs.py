from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
import pygame


SOURCE = Path(__file__).parents[1] / "package_source" / "__init__.py"


def load_module():
    spec = importlib.util.spec_from_file_location("station_tabs_test", SOURCE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def cargo(category: str, name: str) -> dict:
    return {
        "_kind": "cargo",
        "item_category": category,
        "item_key": f"item:{category.lower()}:{name.lower()}",
        "display_name": name,
    }


class StationStorageTabsTests(unittest.TestCase):
    def setUp(self):
        module = load_module()
        self.state = module._StationStorageTabs(SimpleNamespace())
        self.host = SimpleNamespace(
            _station_overlay={
                "kind": "player_station", "body_rect": object()},
            _ps_tab="Storage",
            _ps_station_cargo=[
                cargo("Weapon", "Laser"), cargo("Shield", "Barrier")],
            _ps_storage_search="",
            _ps_storage_scroll=0,
            _ps_storage_rows_cache_key=1,
            _ps_storage_rows_cache=["cached"],
            _ps_storage_filter_cache_key=(1, "x"),
            _ps_storage_filter_cache=["cached"],
            _ps_cargo_popup=None,
            _s=lambda value: value,
            _F=lambda size, bold=False: pygame.font.Font(None, size + 4),
        )
        self.rows = [
            cargo("Weapon", "Laser"),
            cargo("Shield", "Barrier"),
            {"_kind": "plugin_header"},
        ]

    def test_filter_contains_no_synthetic_cargo_rows(self):
        result = self.state._filter_rows(self.host, self.rows)

        self.assertEqual(self.rows, result)
        self.assertFalse(any(
            row.get("_semod_storage_tab_spacer")
            for row in result if isinstance(row, dict)))

    def test_selected_category_filters_cargo_but_keeps_plugin_segment(self):
        self.state.active = "Shield"

        result = self.state._filter_rows(self.host, self.rows)

        self.assertEqual("Barrier", result[0]["display_name"])
        self.assertEqual("plugin_header", result[1]["_kind"])

    def test_inline_region_draw_reserves_real_height_and_publishes_geometry(self):
        pygame.font.init()
        self.state.host = self.host
        self.state.pygame = pygame
        screen = pygame.Surface((800, 600), pygame.SRCALPHA)
        region = pygame.Rect(20, 100, 600, 200)

        used = self.state.draw_region(
            self.host, screen, self.state.REGION, region)

        self.assertEqual(21, used)
        panel = getattr(self.host, self.state.PANEL_ATTR)
        rects = getattr(self.host, self.state.RECTS_ATTR)
        self.assertEqual((20, 100, 600, 21), tuple(panel))
        self.assertEqual(3, len(rects))
        self.assertTrue(all(panel.contains(rect) for _name, rect in rects))

    def test_registration_uses_inline_region_event_only(self):
        module = load_module()
        callbacks = {}
        api = SimpleNamespace(
            loader_api_version=2,
            logger=SimpleNamespace(info=Mock()),
            version="0.1",
            on=lambda event, callback, priority=0: callbacks.setdefault(
                event, callback),
        )

        module.register(api)

        self.assertIn("client.region.draw", callbacks)
        self.assertNotIn("client.draw", callbacks)
        self.assertNotIn("client.frame.begin", callbacks)


if __name__ == "__main__":
    unittest.main()
