"""GUI entry point."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from budget_core import APP_NAME
from budget_gui import theme
from budget_gui.layout_settings import MOTION, LayoutSettings
from budget_gui.main_window import MainWindow
from budget_gui.privacy import disable_settings_files
from budget_gui.theme import Mode, app_icon, apply_theme


def describe_exception(exc_type: type[BaseException], exc: BaseException) -> str:
    """A plain message for an unexpected error: its kind, never its text or a traceback."""
    del exc  # the text may contain project values
    return (
        f"An unexpected error occurred ({exc_type.__name__}). The project files were not "
        "changed by it, but unsaved edits may not have been applied. Save your work, then run "
        "'budget validate' on the project folder; if it keeps happening, report it."
    )


def _excepthook(exc_type: type[BaseException], exc: BaseException, _tb: object) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        return
    if QApplication.instance() is not None:
        box = QMessageBox(QMessageBox.Icon.Critical, APP_NAME, describe_exception(exc_type, exc))
        box.exec()


def create_app(argv: Sequence[str]) -> QApplication:
    sys.excepthook = _excepthook  # no raw tracebacks in a window or a crash dialog
    disable_settings_files()  # Qt's file dialogs would write ~/.config/QtProject.conf (D-105)
    app = QApplication.instance() or QApplication(list(argv))
    assert isinstance(app, QApplication)
    app.setApplicationName(APP_NAME)
    app.setDesktopFileName("system-budget-studio")  # the Linux menu entry (Icon=, D-148)
    layout = LayoutSettings.default()
    saved = layout.word("theme/mode", tuple(m.value for m in Mode), Mode.SYSTEM)
    scales = tuple(str(s) for s in theme.SCALES)
    theme.set_scale_percent(int(layout.word("theme/scale", scales, str(theme.DEFAULT_SCALE))))
    theme.manager().set_reduce_motion(layout.word("theme/motion", MOTION, "full") == "reduced")
    apply_theme(app, Mode(saved))  # light, dark, or whatever the system uses (D-150)
    app.setWindowIcon(app_icon())  # every window and dialog, the task bar included (D-148)
    return app


def main() -> int:
    args = sys.argv[1:]
    if args == ["--self-test"]:  # Qt-free check of a packaged build
        from budget_core.selftest import run_selftest

        failures = run_selftest()
        print("Self-test passed." if not failures else "FAILED: " + "; ".join(failures))
        return 1 if failures else 0
    if args == [
        "--smoke"
    ]:  # a packaged build can create its window (Qt libraries and plugins load)
        from budget_core.selftest import run_selftest

        smoke_app = create_app(sys.argv)
        smoke_window = MainWindow()
        smoke_window.show()
        smoke_app.processEvents()
        failures = run_selftest()
        smoke_window.close()
        print("Smoke test passed." if not failures else "FAILED: " + "; ".join(failures))
        return 1 if failures else 0
    app = create_app(sys.argv)
    window = MainWindow()
    window.show()
    if args and not args[0].startswith("-"):
        window.open_project(Path(args[0]), background=True)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
