# SPDX-FileCopyrightText: 2026 0h3xn4
#
# SPDX-License-Identifier: Apache-2.0

"""No networking: sockets blocked at runtime, networking modules must not be imported.

Each scenario runs in a fresh interpreter so import state is clean.
"""

from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

FORBIDDEN = (
    "http.client",
    "urllib.request",
    "ssl",
    "requests",
    "urllib3",
    "ftplib",
    "smtplib",
    "xmlrpc.client",
    "aiohttp",
    "httpx",
    "PySide6.QtNetwork",
)

PRELUDE = """
import socket, sys
def _blocked(*a, **k):
    raise AssertionError("network access attempted")
socket.socket.connect = _blocked
socket.create_connection = _blocked
socket.getaddrinfo = _blocked
# every other way to resolve a host name or to send a packet (phase 5: the test must fail for any)
for _name in ("gethostbyname", "gethostbyname_ex", "gethostbyaddr", "getnameinfo"):
    setattr(socket, _name, _blocked)
for _name in ("connect_ex", "sendto", "sendmsg"):
    setattr(socket.socket, _name, _blocked)
"""

CHECK = f"""
bad = [m for m in {FORBIDDEN!r} if m in sys.modules]
assert not bad, f"networking modules imported: {{bad}}"
"""


def _run(body: str, allowed: tuple[str, ...] = ()) -> subprocess.CompletedProcess[str]:
    check = CHECK.replace(
        "for m in " + repr(FORBIDDEN),
        "for m in " + repr(tuple(m for m in FORBIDDEN if m not in allowed)),
    )
    code = PRELUDE + textwrap.dedent(body) + check
    env = {"QT_QPA_PLATFORM": "offscreen", "PATH": ""}
    return subprocess.run(
        [sys.executable, "-I", "-c", code], capture_output=True, text=True, env=env, check=False
    )


def test_core_and_cli_do_not_import_network_modules() -> None:
    r = _run("import budget_core, budget_cli.main as m; m.main([])")
    assert r.returncode == 0, r.stderr


def test_loader_validation_and_unit_parsing_do_not_use_the_network() -> None:
    r = _run("""
        import tempfile, pathlib
        from budget_core.examples import export_examples
        from budget_core.io.project_loader import load_project
        from budget_core.units.quantity import parse_quantity
        assert parse_quantity("2.2 GHz", "freq_hz") == 2.2e9  # forces pint
        with tempfile.TemporaryDirectory() as d:
            export_examples(pathlib.Path(d))
            assert load_project(pathlib.Path(d) / "microsat_250kg").project is not None
    """)
    assert r.returncode == 0, r.stderr


def test_gui_starts_offline() -> None:
    r = _run("""
        import sys
        from budget_gui.app import create_app
        from budget_gui.main_window import MainWindow
        app = create_app(["x"]); w = MainWindow(); w.show(); app.processEvents()
    """)
    assert r.returncode == 0, r.stderr


def test_guard_detects_network_use() -> None:
    """Negative test: the harness must fail when a socket is opened or a module imported."""
    r = _run("import socket; socket.create_connection(('127.0.0.1', 9))")
    assert r.returncode != 0
    r = _run("import http.client")
    assert r.returncode != 0


# ReportLab imports these at module level only to fetch images from URLs, which this tool never
# does (it restricts ReportLab to local files). Only the PDF renderer may bring them in (D-043).
REPORTLAB_IMPORTS = ("urllib.request", "http.client", "ssl")


def test_xlsx_and_json_report_path_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        project = {str(tmp_path / "microsat_250kg")!r}
        code = main(["run", project, "--report", "xlsx", "--report", "json",
                     "--report", "csv", "--out", {str(tmp_path / "out")!r}])
        assert code == 0
    """)
    assert r.returncode == 0, r.stderr


def test_pdf_path_imports_only_the_allowed_reportlab_modules_and_never_uses_the_network(
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    r = _run(
        f"""
        import pathlib, urllib.request
        called = []
        orig = urllib.request.urlopen
        urllib.request.urlopen = lambda *a, **k: called.append(a) or orig(*a, **k)
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        code = main(["run", {str(tmp_path / "microsat_250kg")!r}, "--report", "pdf",
                     "--out", {str(tmp_path / "out")!r}])
        assert code == 0 and not called
        from reportlab import rl_config
        assert set(rl_config.trustedSchemes) == {{"file", "data"}}
        assert rl_config.trustedHosts == ["localhost.invalid"]
    """,
        allowed=REPORTLAB_IMPORTS,
    )
    assert r.returncode == 0, r.stderr


def test_reportlab_refuses_remote_resources() -> None:
    r = _run(
        """
        import urllib.request
        called = []
        urllib.request.urlopen = lambda *a, **k: called.append(a)
        import budget_core.reports.pdf
        from reportlab.lib.utils import open_for_read
        try:
            open_for_read("https://example.com/logo.png")
        except OSError:
            pass
        else:
            raise SystemExit("remote resource was opened")
        assert not called, "a network fetch was attempted"
    """,
        allowed=REPORTLAB_IMPORTS,
    )
    assert r.returncode == 0, r.stderr


def test_scenario_command_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        project = {str(tmp_path / "microsat_250kg")!r}
        code = main(["scenario", project, "--out", {str(tmp_path / "out")!r}])
        assert code == 0
    """)
    assert r.returncode == 0, r.stderr


def test_docx_report_path_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        code = main(["run", {str(tmp_path / "microsat_250kg")!r}, "--report", "docx",
                     "--out", {str(tmp_path / "out")!r}])
        assert code == 0
    """)
    assert r.returncode == 0, r.stderr


def test_power_timeline_with_plots_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Plots (Pillow), XLSX, DOCX, JSON and CSV: no networking module is imported. The findings of
    the example (a peak power above its limit) make the exit code 1, which is not a failure here."""
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        code = main(["power-timeline", {str(tmp_path / "microsat_250kg_eps")!r}, "--report", "xlsx",
                     "--report", "docx", "--report", "json", "--report", "csv",
                     "--out", {str(tmp_path / "out")!r}])
        assert code == 1
        assert (pathlib.Path({str(tmp_path / "out")!r}) / "power_time_one_day.docx").exists()
    """)
    assert r.returncode == 0, r.stderr


def test_thermal_budget_path_is_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        code = main(["run", {str(tmp_path / "microsat_250kg_eps")!r}, "--budget", "thermal",
                     "--report", "xlsx", "--report", "docx", "--report", "json",
                     "--report", "csv", "--out", {str(tmp_path / "out")!r}])
        assert code == 1  # the example has a margin finding: not a failure of the guard
    """)
    assert r.returncode == 0, r.stderr


def test_link_budget_paths_are_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    r = _run(f"""
        import pathlib
        from budget_cli.main import main
        from budget_core.examples import export_examples
        export_examples(pathlib.Path({str(tmp_path)!r}))
        project = {str(tmp_path / "microsat_150kg")!r}
        out = {str(tmp_path / "out")!r}
        assert main(["run", project, "--budget", "link", "--report", "xlsx", "--report", "docx",
                     "--report", "json", "--report", "csv", "--out", out]) == 0
        assert main(["link-passes", project, "--report", "xlsx", "--report", "docx",
                     "--report", "json", "--report", "csv", "--out", out]) == 0
    """)
    assert r.returncode == 0, r.stderr


def test_guard_detects_every_name_resolution_and_packet(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """Negative tests: each way of resolving a name or sending a packet must fail the harness."""
    for call in (
        "socket.gethostbyname('example.org')",
        "socket.gethostbyname_ex('example.org')",
        "socket.gethostbyaddr('127.0.0.1')",
        "socket.getnameinfo(('127.0.0.1', 80), 0)",
        "socket.getaddrinfo('example.org', 80)",
        "socket.socket(socket.AF_INET, socket.SOCK_DGRAM).sendto(b'x', ('127.0.0.1', 9))",
        "socket.socket().connect_ex(('127.0.0.1', 9))",
    ):
        assert _run(f"import socket; {call}").returncode != 0, call


def test_spreadsheet_import_idm_import_and_the_guide_are_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The imports (a unit table as XLSX, an IDM-CIC model) and the user guide: no connection."""
    root = Path(__file__).resolve().parents[2]
    r = _run(
        f"""
        import pathlib, sys
        sys.path.insert(0, {str(root)!r})
        from budget_cli.main import main
        from budget_core.examples import export_examples
        from tests.idm.fixtures import model_xml, write_idm
        tmp = pathlib.Path({str(tmp_path)!r})
        export_examples(tmp)
        project = str(tmp / "microsat_250kg")
        table = str(tmp / "units.xlsx")
        assert main(["units-export", project, "--out", table]) == 0
        assert main(["units-import", project, table]) == 0   # a preview, nothing is applied
        model = write_idm(tmp / "model.idm", model_xml())
        main(["import", "idm", str(model), "--bus-voltage-v", "28"])  # a plan, nothing is written
        assert main(["guide", "--out", str(tmp / "guide")]) == 0
    """,
        allowed=REPORTLAB_IMPORTS,  # the guide has a PDF: ReportLab imports these (D-043)
    )
    assert r.returncode == 0, r.stderr


def test_window_actions_are_strictly_offline(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """The window after the start: a project, the guide, About, the licences and the settings."""
    root = Path(__file__).resolve().parents[2]
    r = _run(f"""
        import pathlib, sys
        sys.path.insert(0, {str(root)!r})
        from budget_core.examples import export_examples
        from budget_gui.app import create_app
        from budget_gui.main_window import MainWindow
        tmp = pathlib.Path({str(tmp_path)!r})
        export_examples(tmp)
        app = create_app(["x"]); w = MainWindow(); w.show(); app.processEvents()
        assert w.open_project(tmp / "microsat_250kg_eps")
        for dialog in (w.open_guide(), w.open_about(), w.open_notices()):
            app.processEvents(); dialog.close()
        popover = w.show_settings(); app.processEvents(); popover.close()
        w.discard_all_changes() if hasattr(w, "discard_all_changes") else None
    """)
    assert r.returncode == 0, r.stderr
