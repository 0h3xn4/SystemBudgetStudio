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


SWITCH_INTERVAL_S = 0.0005  # how long a thread may keep the interpreter lock when another waits


def create_app(argv: Sequence[str]) -> QApplication:
    sys.excepthook = _excepthook  # no raw tracebacks in a window or a crash dialog
    # The window thread needs the lock for every paint and every slot; the default 5 ms wait per
    # hand-over turns a burst of them into a visible stall while a worker computes (D-183).
    sys.setswitchinterval(SWITCH_INTERVAL_S)
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


def split_options(args: Sequence[str]) -> tuple[list[str], Path | None, bool, Path | None]:
    """The arguments without the two support options of D-257, and those options: the file of
    `--fault-log FILE`, and whether `--diagnose [FILE]` was given with its file."""
    rest: list[str] = []
    fault_log: Path | None = None
    diagnose = False
    diagnose_file: Path | None = None
    i = 0
    while i < len(args):
        arg = args[i]
        has_value = i + 1 < len(args) and not args[i + 1].startswith("-")
        if arg == "--fault-log" and has_value:
            fault_log = Path(args[i + 1])
            i += 2
        elif arg == "--diagnose":
            diagnose = True
            if has_value:
                diagnose_file = Path(args[i + 1])
                i += 1
            i += 1
        else:
            rest.append(arg)
            i += 1
    return rest, fault_log, diagnose, diagnose_file


def run_diagnose(file: Path | None) -> int:
    """Print what Qt and the program know about this machine; also write it to `file`, because
    the windowed program has no console on Windows."""
    from budget_gui.diagnostics import report

    text = report(create_app(sys.argv[:1]))
    if file is not None:
        file.write_text(text, encoding="utf-8")
    if sys.stdout is not None:
        print(text, end="")
    return 0


def main() -> int:
    args, fault_log, diagnose, diagnose_file = split_options(sys.argv[1:])
    if fault_log is not None:  # first of all: a crash while the program starts is caught too
        from budget_core.diagnostics import enable_fault_log

        enable_fault_log(fault_log)
    if diagnose:
        return run_diagnose(diagnose_file)
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
