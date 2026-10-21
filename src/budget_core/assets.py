"""Location of the bundled assets (the fonts of the window and of exported files, licences,
application icons).

No network, no downloads."""

from __future__ import annotations

from pathlib import Path


def assets_dir() -> Path:
    """Installed wheel, source checkout or PyInstaller bundle, in that order."""
    here = Path(__file__).resolve().parent
    for candidate in (here / "assets", here.parent.parent / "assets"):
        if (candidate / "fonts").is_dir():
            return candidate
    raise FileNotFoundError("Bundled assets folder not found; the installation is incomplete.")


def font_path(name: str) -> Path:
    return assets_dir() / "fonts" / name


def icon_files() -> list[Path]:
    """The application icon as PNG files of several sizes (assets/icons/logo-<size>.png), the
    smallest first; an empty list when the folder is missing (the window then has no icon)."""
    try:
        folder = assets_dir() / "icons"
    except FileNotFoundError:
        return []
    return sorted(folder.glob("logo-*.png"), key=lambda path: int(path.stem.split("-")[1]))


def ui_icon_files(name: str) -> dict[int, Path]:
    """The black PNG mask of a user-interface icon by size (assets/icons/ui/<name>-<size>.png);
    empty when the icon or the folder is missing."""
    try:
        folder = assets_dir() / "icons" / "ui"
    except FileNotFoundError:
        return {}
    found: dict[int, Path] = {}
    for path in folder.glob(f"{name}-*.png"):
        size = path.stem.rsplit("-", 1)[-1]
        if size.isdigit() and path.stem == f"{name}-{size}":
            found[int(size)] = path
    return dict(sorted(found.items()))
