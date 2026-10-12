"""MI-4 guard: a message or hint of a Problem may interpolate only names that hold ids, counts,
codes or constants, never a name read from a project file.

The leak test (test_audit_no_leak.py) finds leaks that the example projects can trigger; this one
reads the source so a new f-string cannot bring a free-text name back unnoticed. To interpolate a
new variable, add it to SAFE below and say in the comment why it holds no file content.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "budget_core"

SAFE = {
    "uid",  # a unit id: the file name in units/
    "row.item_id",  # a unit or expendable id: the file name
    "sid",  # a site id (file name)
    "oid",  # an orbit id (file name)
    "link_id",  # a link id (file name)
    "scenario_id",  # a scenario id (file name) or what the user typed on the command line
    "known",  # a sorted list of file-name ids
    "kind",  # a file kind from the code
    "side",  # "transmitter" / "receiver" / "spacecraft" / "ground" from the code
    "limit_set",  # "operating" / "survival"
    "what",  # a constant phrase from the caller (checked by test_audit_no_leak)
    "file",  # a file path inside the project
    "FILE",
    "where",  # a constant phrase built by the caller
    "reason",  # a fixed reason from check_orbit
    "allowed",  # a numeric range
    "index",
    "i",
    "position",
    "phase_number",
    "version",
    "start",
    "target",
    "version + 1",
    "len(items)",
    "format_offset(first.start_s)",
    "_MESSAGES[code]",
    "exc",  # YamlSyntaxError / EnvironmentInputError: fixed texts that never echo content
}


def _messages(tree: ast.AST) -> list[tuple[int, ast.expr]]:
    found: list[tuple[int, ast.expr]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
        picks: list[ast.expr] = []
        if name == "Problem":
            picks += node.args[2:3]
        elif name == "incomplete":
            picks += node.args[:1]
        elif name == "_p":
            picks += node.args[2:3] + node.args[6:7]
        else:
            continue
        picks += [k.value for k in node.keywords if k.arg in ("message", "hint")]
        found += [(node.lineno, p) for p in picks]
    return found


def test_problem_texts_interpolate_only_safe_names() -> None:
    bad: list[str] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for _line, expr in _messages(tree):
            for sub in ast.walk(expr):
                if isinstance(sub, ast.FormattedValue):
                    text = ast.unparse(sub.value)
                    if text not in SAFE:
                        bad.append(f"{path.relative_to(SRC)}:{sub.lineno}: {{{text}}}")
    assert not bad, "\n".join(bad)
