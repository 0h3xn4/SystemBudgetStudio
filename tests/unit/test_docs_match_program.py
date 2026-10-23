"""The documentation says what the program does (a check that runs with the unit tests).

Four things are read from the pages and held against the program, so a page cannot drift without a
test failing: every `budget ...` command shown in a code block is read by the real argument parser,
every option of every command is described in the command-line reference, every field of every
JSON Schema is named in a page about file formats, and every page is linked from another page.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import re
import shlex
from pathlib import Path

from budget_cli.main import build_parser

ROOT = Path(__file__).resolve().parents[2]
# the records of what was decided or found are history, not instructions to follow
HISTORY = {"CHANGELOG.md", "DECISIONS.md", "DOCS_AUDIT.md", "AUDIT.md", "SPEC.md"}


def _pages() -> list[Path]:
    found = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", ROOT / "examples" / "README.md"]
    found += sorted((ROOT / "docs").rglob("*.md"))
    found += sorted((ROOT / "src" / "budget_core" / "guide" / "chapters").glob("*.md"))
    return [p for p in found if p.name not in HISTORY and "demo" not in p.parts]


def _shown_commands() -> list[tuple[str, list[str]]]:
    """Every `budget ...` line of a fenced code block, as (page, argv). A line that continues on
    the next one is joined; a trailing comment, a redirection, a pipe and a usage synopsis (with
    square brackets or capitals standing for a value) are not commands to read."""
    commands: list[tuple[str, list[str]]] = []
    for page in _pages():
        text = page.read_text(encoding="utf-8")
        for block in re.findall(r"```[a-z]*\n(.*?)```", text, flags=re.S):
            lines = block.split("\n")
            for number, line in enumerate(lines):
                match = re.match(r"^\s*(?:\$ |> )?budget (.+)$", line)
                if match is None:
                    continue
                command = match.group(1)
                follow = number
                while command.rstrip().endswith("\\") and follow + 1 < len(lines):
                    follow += 1
                    command = command.rstrip()[:-1] + " " + lines[follow].strip()
                command = re.sub(r"\s+#.*$", "", command)
                if re.search(r"[|>\[\]]|…|\.\.\.", command):
                    continue
                try:
                    argv = shlex.split(command)
                except ValueError:
                    continue
                if argv and not argv[0].startswith("-"):
                    commands.append((str(page.relative_to(ROOT)), argv))
    return commands


def test_every_command_shown_in_the_docs_is_read_by_the_parser() -> None:
    parser = build_parser()
    commands = _shown_commands()
    assert len(commands) > 30  # the extraction works: the pages show dozens of commands
    refused: list[str] = []
    for page, argv in commands:
        stderr = io.StringIO()
        try:
            with contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
                parser.parse_args(argv)
        except SystemExit as exit_:
            if exit_.code not in (0, None):
                refused.append(f"{page}: budget {' '.join(argv)}")
    assert not refused, "commands the parser does not accept:\n" + "\n".join(refused)


def test_every_option_of_every_command_is_in_the_command_line_reference() -> None:
    reference = (ROOT / "docs" / "user-manual" / "command-line.md").read_text(encoding="utf-8")
    parser = build_parser()
    subparsers = next(a for a in parser._actions if isinstance(a, argparse._SubParsersAction))
    missing = [
        f"{name} {option}"
        for name, sub in subparsers.choices.items()
        for action in sub._actions
        for option in action.option_strings
        if option.startswith("--") and option != "--help" and option not in reference
    ]
    assert not missing, f"options missing from docs/user-manual/command-line.md: {missing}"


def _schema_fields(node: object, found: set[str]) -> set[str]:
    if isinstance(node, dict):
        for name, value in node.get("properties", {}).items():
            found.add(name)
            _schema_fields(value, found)
        for key in ("items", "additionalProperties"):
            if key in node:
                _schema_fields(node[key], found)
        for key in ("$defs", "definitions"):
            for value in node.get(key, {}).values():
                _schema_fields(value, found)
        for key in ("anyOf", "oneOf", "allOf"):
            for value in node.get(key, []):
                _schema_fields(value, found)
    return found


def test_every_field_of_every_schema_is_named_in_a_page_about_file_formats() -> None:
    import json

    pages = "\n".join(
        (ROOT / "docs" / name).read_text(encoding="utf-8")
        for name in ("FILE_FORMAT.md", "ENVIRONMENT_FORMAT.md")
    )
    pages += "\n" + (ROOT / "docs" / "user-manual" / "scenarios.md").read_text(encoding="utf-8")
    missing: dict[str, list[str]] = {}
    for schema in sorted((ROOT / "src" / "budget_core" / "schemas").glob("*.schema.json")):
        fields = _schema_fields(json.loads(schema.read_text(encoding="utf-8")), set())
        absent = sorted(f for f in fields if not re.search(rf"\b{re.escape(f)}\b", pages))
        if absent:
            missing[schema.name] = absent
    assert not missing, f"fields no file-format page names: {missing}"


def test_every_page_is_linked_from_another_page() -> None:
    tracked = [p for p in (ROOT / "docs").rglob("*.md") if "demo" not in p.parts] + [
        ROOT / "CONTRIBUTING.md",
        ROOT / "examples" / "README.md",
    ]
    linked: set[Path] = set()
    for page in [*tracked, ROOT / "README.md", *_pages()]:
        for target in re.findall(r"\]\(([^)#\s]+\.md)(?:#[^)]*)?\)", page.read_text("utf-8")):
            linked.add((page.parent / target).resolve())
    orphans = sorted(str(p.relative_to(ROOT)) for p in tracked if p.resolve() not in linked)
    assert not orphans, f"pages that no page links to: {orphans}"
