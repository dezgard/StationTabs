"""Category tabs for the player-owned station Storage view."""

from __future__ import annotations

from typing import Any


class _StationStorageTabs:
    ALL = "All"
    MAX_COLUMNS = 6
    MAX_ROWS = 4
    NATIVE_ROW_HEIGHT = 21
    REGION = "player_station.storage.filters"
    RECTS_ATTR = "_ps_semod_storage_tab_rects"
    PANEL_ATTR = "_ps_semod_storage_tab_panel_rect"

    def __init__(self, api: Any) -> None:
        self.api = api
        self.host = None
        self.pygame = None
        self.active = self.ALL
        self.method_owner = None
        self.original_builder = None
        self.builder_wrapper = None

    @staticmethod
    def _row_category(row: Any) -> str:
        if not isinstance(row, dict):
            return "Other"
        for field in ("item_category", "item_class"):
            value = str(row.get(field, "") or "").strip()
            if value:
                return value.replace("_", " ").title()
        if not str(row.get("item_key", "") or "").startswith("item:"):
            return "Resources"
        return "Other"

    def _categories(self, host: Any) -> list[str]:
        cargo = getattr(host, "_ps_station_cargo", None) or ()
        found = {
            self._row_category(row)
            for row in cargo
            if isinstance(row, dict)
        }
        return [self.ALL, *sorted(found, key=str.casefold)]

    def _active_category(self, host: Any) -> str:
        categories = self._categories(host)
        if self.active not in categories:
            self.active = self.ALL
        return self.active

    @staticmethod
    def _visible(host: Any) -> bool:
        overlay = getattr(host, "_station_overlay", None)
        return (
            isinstance(overlay, dict)
            and overlay.get("kind") == "player_station"
            and getattr(host, "_ps_tab", "") == "Storage"
            and overlay.get("body_rect") is not None
        )

    @staticmethod
    def _invalidate_rows(host: Any) -> None:
        for name in (
            "_ps_storage_rows_cache_key",
            "_ps_storage_rows_cache",
            "_ps_storage_filter_cache_key",
            "_ps_storage_filter_cache",
        ):
            if hasattr(host, name):
                setattr(host, name, None)

    @classmethod
    def _invalidate(cls, host: Any) -> None:
        cls._invalidate_rows(host)
        if hasattr(host, "_ps_storage_scroll"):
            host._ps_storage_scroll = 0
        if hasattr(host, "_ps_cargo_popup"):
            host._ps_cargo_popup = None

    def _grid_rows(self, host: Any) -> int:
        count = max(1, len(self._categories(host)))
        return max(1, min(
            self.MAX_ROWS,
            (count + self.MAX_COLUMNS - 1) // self.MAX_COLUMNS,
        ))

    def _filter_rows(self, host: Any, rows: Any) -> list:
        source = list(rows or ())
        active = self._active_category(host)
        if active == self.ALL:
            filtered = source
        else:
            filtered = [
                row for row in source
                if not isinstance(row, dict)
                or row.get("_kind") != "cargo"
                or self._row_category(row) == active
            ]
            if not any(
                isinstance(row, dict) and row.get("_kind") == "cargo"
                for row in filtered
            ):
                insert_at = next(
                    (
                        index for index, row in enumerate(filtered)
                        if isinstance(row, dict)
                        and row.get("_kind") in {
                            "plugin_header", "plugin_slot"}
                    ),
                    len(filtered),
                )
                if not any(
                    isinstance(row, dict) and row.get("_kind") == "empty"
                    for row in filtered
                ):
                    filtered.insert(insert_at, {"_kind": "empty"})

        return filtered

    @classmethod
    def _clear_geometry(cls, host: Any) -> None:
        if host is None:
            return
        setattr(host, cls.RECTS_ATTR, [])
        setattr(host, cls.PANEL_ATTR, None)

    @staticmethod
    def _find_method_owner(host_type: type, method_name: str) -> type | None:
        return next(
            (
                owner for owner in host_type.__mro__
                if method_name in owner.__dict__
            ),
            None,
        )

    def install(self, host: Any, pygame: Any) -> None:
        if self.host is not None:
            if self.host is host:
                return
            raise RuntimeError("Station Storage Tabs is already attached")
        owner = self._find_method_owner(type(host), "_build_ps_storage_rows")
        original = None if owner is None else owner.__dict__.get(
            "_build_ps_storage_rows")
        if owner is None or not callable(original):
            raise RuntimeError("compatible station storage builder is unavailable")
        state = self

        def builder_wrapper(instance, *args, **kwargs):
            rows = original(instance, *args, **kwargs)
            if instance is state.host:
                try:
                    return state._filter_rows(instance, rows)
                except Exception:
                    state.api.logger.exception("station storage filter failed")
            return rows

        self.host = host
        self.pygame = pygame
        self.method_owner = owner
        self.original_builder = original
        self.builder_wrapper = builder_wrapper
        setattr(owner, "_build_ps_storage_rows", builder_wrapper)
        self._invalidate(host)
        self._clear_geometry(host)

    def uninstall(self) -> None:
        if (
            self.method_owner is not None
            and getattr(self.method_owner, "_build_ps_storage_rows", None)
            is self.builder_wrapper
        ):
            setattr(
                self.method_owner,
                "_build_ps_storage_rows",
                self.original_builder,
            )
        self._clear_geometry(self.host)
        self.host = None
        self.pygame = None
        self.method_owner = None

    @staticmethod
    def _fit_label(font: Any, label: str, width: int) -> str:
        if font.size(label)[0] <= width:
            return label
        shortened = label
        while shortened and font.size(shortened + "...")[0] > width:
            shortened = shortened[:-1]
        return shortened + "..." if shortened else ""

    def draw_region(
            self, host: Any, screen: Any, region: str, rect: Any) -> int:
        if region != self.REGION:
            return 0
        self._clear_geometry(host)
        if not self._visible(host) or screen is None:
            return 0
        if str(getattr(host, "_ps_storage_search", "") or "").strip():
            return 0
        if rect is None or not hasattr(screen, "get_size"):
            return 0

        pygame = self.pygame
        categories = self._categories(host)
        active = self._active_category(host)
        screen_width, screen_height = screen.get_size()
        scale = getattr(host, "_s", lambda value: value)
        tab_height = max(1, int(scale(self.NATIVE_ROW_HEIGHT)))
        x = max(0, int(getattr(rect, "x", 0)))
        y = max(0, int(getattr(rect, "y", 0)))
        width = min(
            max(1, int(getattr(rect, "width", 0))),
            max(0, int(screen_width) - x),
        )
        columns = max(1, min(len(categories), self.MAX_COLUMNS))
        rows = (len(categories) + self.MAX_COLUMNS - 1) // self.MAX_COLUMNS
        if rows > self.MAX_ROWS:
            return 0
        height = rows * tab_height
        available_height = max(0, int(getattr(rect, "height", 0)))
        if (width < 1 or height > available_height
                or y + height > int(screen_height)):
            return 0

        panel = pygame.Surface((width, height), pygame.SRCALPHA)
        panel.fill((5, 10, 16, 235))
        pygame.draw.rect(panel, (55, 95, 130, 235), panel.get_rect(), 1)
        font_factory = getattr(host, "_F", None)
        font = (
            font_factory(10, bold=True)
            if callable(font_factory)
            else pygame.font.SysFont("segoeui", 10, bold=True)
        )
        tab_width = max(1, width // columns)
        published_rects = []

        for index, category in enumerate(categories):
            column = index % self.MAX_COLUMNS
            row = index // self.MAX_COLUMNS
            left = column * tab_width
            right = width if column == columns - 1 else left + tab_width
            local = pygame.Rect(
                left,
                row * tab_height,
                max(1, right - left),
                tab_height,
            )
            selected = category == active
            fill = (10, 48, 72, 245) if selected else (8, 20, 31, 225)
            border = (90, 185, 245) if selected else (65, 100, 130)
            pygame.draw.rect(panel, fill, local)
            pygame.draw.rect(panel, border, local, 1)
            label = self._fit_label(font, category, max(1, tab_width - 8))
            text = font.render(label, True, border)
            panel.blit(
                text,
                (
                    local.centerx - text.get_width() // 2,
                    local.centery - text.get_height() // 2,
                ),
            )
            published_rects.append((category, local.move(x, y)))
        screen.blit(panel, (x, y))
        setattr(host, self.RECTS_ATTR, published_rects)
        setattr(host, self.PANEL_ATTR, pygame.Rect(x, y, width, height))
        return height

    def handle_event(self, host: Any, event: Any) -> bool:
        if not self._visible(host):
            self._clear_geometry(host)
            return False
        pygame = self.pygame
        panel_rect = getattr(host, self.PANEL_ATTR, None)
        rects = getattr(host, self.RECTS_ATTR, ())
        if panel_rect is None:
            return False
        point = getattr(event, "pos", None)
        if point is None:
            point = pygame.mouse.get_pos()
        if not panel_rect.collidepoint(point):
            return False
        event_type = getattr(event, "type", None)
        if event_type == getattr(pygame, "MOUSEWHEEL", None):
            return True
        if event_type != pygame.MOUSEBUTTONDOWN:
            return False
        if getattr(event, "button", None) != 1:
            return True
        for category, rect in rects:
            if not rect.collidepoint(point):
                continue
            if category != self._active_category(host):
                self.active = category
                self._invalidate(host)
            return True
        return True


def register(api: Any) -> None:
    """Register Station Storage Tabs with Star Empire Mod Loader API 2."""
    if getattr(api, "loader_api_version", 0) < 2:
        raise RuntimeError("Station Storage Tabs requires loader API 2")
    state = _StationStorageTabs(api)

    def startup(*, host: Any, pygame: Any, **_kwargs) -> bool:
        state.install(host, pygame)
        api.logger.info("STATION_STORAGE_TABS_STARTED version=%s", api.version)
        return True

    def event(*, host: Any, event: Any, **_kwargs) -> bool:
        return state.host is host and state.handle_event(host, event)

    def draw_region(
            *, host: Any, screen: Any, region: str, rect: Any,
            **_kwargs) -> int:
        if state.host is host:
            return state.draw_region(host, screen, region, rect)
        return 0

    api.on("client.startup", startup, priority=450)
    api.on("client.event", event, priority=450)
    api.on("client.region.draw", draw_region, priority=450)
    api.on(
        "loader.shutdown",
        lambda *_args, **_kwargs: state.uninstall(),
        priority=450,
    )


__all__ = ("register",)
