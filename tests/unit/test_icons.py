"""The icon files in assets/icons are what packaging/make_icons.py draws (D-148)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image, ImageChops

from budget_core.assets import icon_files

ROOT = Path(__file__).resolve().parents[2]


def load_make_icons():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(
        "make_icons", ROOT / "packaging" / "make_icons.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["make_icons"] = module
    spec.loader.exec_module(module)
    return module


def test_the_committed_icons_are_what_the_script_draws() -> None:
    make = load_make_icons()
    files = icon_files()
    assert [int(f.stem.split("-")[1]) for f in files] == list(make.SIZES)
    for file in files:
        size = int(file.stem.split("-")[1])
        drawn = make.draw(size)
        committed = Image.open(file).convert("RGBA")
        assert committed.size == drawn.size
        # a different Pillow may resample a pixel by a level or two; a changed drawing is far more
        difference = ImageChops.difference(committed, drawn).getextrema()
        assert max(high for _low, high in difference) <= 3, f"{file.name} is out of date"


def test_the_svg_and_the_script_agree_on_the_bars() -> None:
    make = load_make_icons()
    svg = (ROOT / "docs" / "images" / "logo.svg").read_text(encoding="utf-8")
    for x, y, w, h, colour in make.BARS:
        assert f'x="{x}" y="{y}" width="{w}" height="{h}" fill="{colour}"' in svg


def test_the_windows_icon_holds_every_size_each_drawn_on_its_own() -> None:
    make = load_make_icons()
    with Image.open(ROOT / "assets" / "icons" / "logo.ico") as ico:
        assert sorted(ico.ico.sizes()) == [(n, n) for n in make.SIZES]
        for size in make.SIZES:
            frame = ico.ico.getimage((size, size)).convert("RGBA")
            difference = ImageChops.difference(frame, make.draw(size)).getextrema()
            assert max(high for _low, high in difference) <= 3, f"{size} px is a scaled copy"


def test_the_packaging_files_use_the_icon() -> None:
    spec = (ROOT / "packaging" / "system_budget_studio.spec").read_text(encoding="utf-8")
    assert spec.count("icon=icon") == 2 and "logo.ico" in spec  # both executables
    inno = (ROOT / "packaging" / "windows" / "system_budget_studio.iss").read_text(encoding="utf-8")
    assert "SetupIconFile=..\\..\\assets\\icons\\logo.ico" in inno
    assert (ROOT / "assets" / "icons" / "logo.ico").is_file()
