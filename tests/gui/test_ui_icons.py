"""The user-interface icons: Lucide SVG sources, black PNG masks made from them (D-150)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from budget_core.assets import assets_dir, ui_icon_files
from budget_gui import theme

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "assets" / "icons" / "ui"


def load_script():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "make_ui_icons", ROOT / "packaging" / "make_ui_icons.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_ui_icons"] = module
    spec.loader.exec_module(module)
    return module


def test_every_icon_has_all_sizes_and_the_status_icons_exist() -> None:
    script = load_script()
    names = script.names()
    assert len(names) >= 30
    for name in names:
        assert sorted(ui_icon_files(name)) == list(script.SIZES), name
    for icon in theme.STATUS_ICONS.values():
        assert icon in names, icon


def test_the_licence_and_the_origin_of_the_icons_are_kept() -> None:
    licence = (FOLDER / "LICENSE-Lucide.txt").read_text(encoding="utf-8")
    assert licence.startswith("ISC License")
    assert "0.468.0" in (FOLDER / "README.md").read_text(encoding="utf-8")
    assert (assets_dir() / "icons" / "ui").is_dir()


def test_the_sources_are_plain_svg_drawings() -> None:
    allowed = {"svg", "path", "circle", "rect", "line", "polyline", "polygon", "ellipse"}
    import xml.etree.ElementTree as ET

    for path in sorted((FOLDER / "src").glob("*.svg")):
        root = ET.parse(path).getroot()  # noqa: S314 - our own committed files
        tags = {element.tag.split("}")[-1] for element in root.iter()}
        assert tags <= allowed, (path.name, tags - allowed)
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in ("<script", "onload", "javascript:", "<style", "href"):
            assert forbidden not in text, (path.name, forbidden)


def test_the_committed_masks_are_what_the_script_renders(qtbot) -> None:  # type: ignore[no-untyped-def]
    from PySide6.QtGui import QImage

    script = load_script()
    for name in ("circle-check", "triangle-alert", "play", "search"):
        svg = (FOLDER / "src" / f"{name}.svg").read_bytes()
        for size in script.SIZES:
            drawn = script.render(svg, size)
            committed = QImage(str(FOLDER / f"{name}-{size}.png")).convertToFormat(drawn.format())
            assert committed.size() == drawn.size()
            worst = max(
                abs(committed.pixelColor(x, y).alpha() - drawn.pixelColor(x, y).alpha())
                for x in range(size)
                for y in range(size)
            )
            assert worst <= 12, (name, size, worst)  # antialiasing may differ a little


def test_a_mask_is_black_so_the_tint_decides_the_colour() -> None:
    from PySide6.QtGui import QImage

    image = QImage(str(FOLDER / "circle-check-48.png"))
    for x in range(image.width()):
        for y in range(image.height()):
            c = image.pixelColor(x, y)
            if c.alpha() > 0:
                assert (c.red(), c.green(), c.blue()) == (0, 0, 0)


@pytest.mark.parametrize("size", [16, 24, 32, 48])
def test_the_lookup_finds_a_size(size: int) -> None:
    assert size in ui_icon_files("play") and ui_icon_files("no-such") == {}
