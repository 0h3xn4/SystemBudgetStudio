"""The project tree: the spacecraft model, not the folder listing, with problem badges (D-151).

    Project
      Spacecraft          units (and their power modes), spacecraft modes, solar array, battery
      Orbit & ground stations
      Scenarios
      Links               each with its transmitter and receiver (the antennas)
      Budget configuration
      Files               every project file, for the expert who wants the raw list

A node opens the file that holds it (a field node jumps to the line of the field). Each node
carries the count of the problems that belong to it, by class, drawn as a small badge with an icon
and a number, so a placeholder or an error is visible on the node before the node is opened.
The tree is built from the files of the folder and, when the project loads, from its names.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QPersistentModelIndex, QRect, Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QApplication,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeWidget,
    QTreeWidgetItem,
)

from budget_core.model import Project
from budget_core.problems import Problem
from budget_gui import icons
from budget_gui import problem_class as pc
from budget_gui.problem_class import ProblemClass

FILE_ROLE = int(Qt.ItemDataRole.UserRole)  # relative path of the file the node opens
UNIT_ROLE = FILE_ROLE + 1  # id of the unit a node belongs to
PATH_ROLE = FILE_ROLE + 2  # field inside the file ("" for the whole file)
KIND_ROLE = FILE_ROLE + 3  # "file", "field", "unit_modes" or "group"
BADGE_ROLE = FILE_ROLE + 4  # tuple of (class value, count)
NODE_ROLE = FILE_ROLE + 5  # index of the node in the tree's list of nodes
Index = QModelIndex | QPersistentModelIndex

CONFIG_FOLDER = "config"
BADGE_CLASSES = (ProblemClass.ERROR, ProblemClass.WARNING, ProblemClass.NOT_CHECKED)


@dataclass
class Node:
    """One tree row, as data (no widgets), so the structure can be tested on its own."""

    label: str
    kind: str = "group"  # "file", "raw_file", "field", "unit_modes", "group", "project"
    rel: str = ""
    path: str = ""
    unit_id: str = ""
    expanded: bool = False
    own_problems: bool = False  # count the problems of (rel, path) on this node
    children: list[Node] = field(default_factory=list)

    def walk(self) -> Iterable[Node]:
        yield self
        for child in self.children:
            yield from child.walk()


def _yaml_files(root: Path, folder: str) -> list[Path]:
    directory = root / folder
    return sorted(directory.glob("*.yaml")) if directory.is_dir() else []


def _group(title: str, files: list[Path], folder: str) -> Node | None:
    if not files:
        return None
    group = Node(f"{title} ({len(files)})", expanded=True)
    for path in files:
        group.children.append(Node(path.stem, "file", f"{folder}/{path.name}", own_problems=True))
    return group


def build_nodes(root: Path, project: Project | None) -> Node:
    """The tree of a project folder. `project` (when it loaded) supplies names and the units whose
    power modes can be edited; without it the tree is made from the files."""
    name = project.meta.name if project else root.name
    revision = f"  ·  rev {project.meta.revision}" if project else ""
    top = Node(f"{name}{revision}", "project", "project.yaml", expanded=True)

    spacecraft = Node("Spacecraft", "file", "spacecraft.yaml", expanded=True, own_problems=True)
    if not (root / "spacecraft.yaml").is_file():
        spacecraft.kind, spacecraft.rel = "group", ""
    unit_files = _yaml_files(root, "units")
    if unit_files:
        units = Node(f"Units ({len(unit_files)})", expanded=True)
        for path in unit_files:
            unit = project.units.get(path.stem) if project else None
            label = f"{path.stem}: {unit.name}" if unit else path.stem
            node = Node(label, "file", f"units/{path.name}", unit_id=path.stem, own_problems=True)
            if unit:
                node.children.append(
                    Node(
                        f"Power modes ({len(unit.modes)})",
                        "unit_modes",
                        node.rel,
                        "modes",
                        unit_id=path.stem,
                    )
                )
            units.children.append(node)
        spacecraft.children.append(units)
    modes = _group("Spacecraft modes", _yaml_files(root, "modes"), "modes")
    if modes:
        spacecraft.children.append(modes)
    expendables = _group("Expendables", _yaml_files(root, "expendables"), "expendables")
    if expendables:
        expendables.expanded = False
        spacecraft.children.append(expendables)
    if (root / "config" / "power_system.yaml").is_file():
        for label, key in (("Solar array", "solar_array"), ("Battery", "battery")):
            spacecraft.children.append(
                Node(label, "field", "config/power_system.yaml", key, own_problems=True)
            )
    if spacecraft.children or spacecraft.rel:
        top.children.append(spacecraft)

    sites = Node("Orbit & ground stations", expanded=True)
    for folder, title in (
        ("orbits", "Orbits"),
        ("ground_stations", "Ground stations"),
        ("targets", "Imaging targets"),
    ):
        group = _group(title, _yaml_files(root, folder), folder)
        if group:
            sites.children.append(group)
    if sites.children:
        top.children.append(sites)

    scenarios = _group("Scenarios", _yaml_files(root, "scenarios"), "scenarios")
    if scenarios:
        top.children.append(scenarios)

    link_files = _yaml_files(root, "links")
    if link_files:
        links = Node(f"Links ({len(link_files)})", expanded=True)
        for path in link_files:
            link = project.links.get(path.stem) if project else None
            label = f"{path.stem}: {link.name}" if link else path.stem
            rel = f"links/{path.name}"
            node = Node(label, "file", rel, own_problems=True)
            node.children.append(
                Node("Transmitter", "field", rel, "transmitter", own_problems=True)
            )
            node.children.append(Node("Receiver", "field", rel, "receiver", own_problems=True))
            links.children.append(node)
        top.children.append(links)

    config = _group("Budget configuration", _yaml_files(root, CONFIG_FOLDER), CONFIG_FOLDER)
    if config:
        config.expanded = False
        top.children.append(config)

    files = Node("Files", expanded=False)
    for rel in all_files(root):
        files.children.append(Node(rel, "raw_file", rel, own_problems=True))
    if files.children:
        files.label = f"Files ({len(files.children)})"
        top.children.append(files)
    return top


def all_files(root: Path) -> list[str]:
    found = [p.relative_to(root).as_posix() for p in sorted(root.rglob("*.yaml")) if p.is_file()]
    return found


def _belongs(problem: Problem, node: Node) -> bool:
    if not node.own_problems or problem.file != node.rel:
        return False
    if not node.path:
        return True
    return (
        problem.path == node.path
        or problem.path.startswith(node.path + ".")
        or problem.path.startswith(node.path + "[")
    )


def problems_of(node: Node, problems: Iterable[Problem]) -> list[Problem]:
    """The problems that belong to a node, in the order given: those of its own file and field and
    of its children (the project node: all of them, also those without a file)."""
    listed = list(problems)
    if node.kind == "project":
        return listed
    if node.kind == "unit_modes":
        return [p for p in listed if p.file == node.rel and p.path.startswith(node.path)]
    members = [n for n in node.walk() if n.kind != "unit_modes"]
    return [p for p in listed if any(_belongs(p, n) for n in members)]


def badge_counts(top: Node, problems: Iterable[Problem]) -> dict[int, dict[ProblemClass, int]]:
    """Problems per class for every node (by `id(node)`). A node counts the problems of its own
    file and field plus those of its children; the project node counts every problem."""
    listed = list(problems)
    result: dict[int, dict[ProblemClass, int]] = {}

    def count(node: Node) -> dict[ProblemClass, int]:
        total = pc.counts(p for p in listed if _belongs(p, node))
        for child in node.children:
            if child.kind == "unit_modes":
                continue  # its problems are the unit's own
            for cls, number in count(child).items():
                total[cls] += number
        result[id(node)] = total
        return total

    count(top)
    result[id(top)] = pc.counts(listed)  # the project node: everything, also what has no file
    for node in top.walk():
        if node.kind == "unit_modes":
            result[id(node)] = {cls: 0 for cls in ProblemClass}
    return result


class BadgeDelegate(QStyledItemDelegate):
    """Draws the row, then the problem badges (icon and number) at its right edge."""

    ICON = 14
    GAP = 6

    def _badges(self, index: Index) -> list[tuple[ProblemClass, int]]:
        raw = index.data(BADGE_ROLE) or ()
        return [(ProblemClass(c), int(n)) for c, n in raw if n]

    def _width(self, badges: list[tuple[ProblemClass, int]], option: Any) -> int:
        width = 0
        for _cls, number in badges:
            width += self.ICON + 2 + option.fontMetrics.horizontalAdvance(str(number)) + self.GAP
        return width

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: Index) -> None:
        opt: Any = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        badges = self._badges(index)
        reserved = self._width(badges, opt)
        if reserved:
            room = max(opt.rect.width() - reserved - 24, 20)
            opt.text = opt.fontMetrics.elidedText(opt.text, Qt.TextElideMode.ElideRight, room)
        style = opt.widget.style() if opt.widget else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)
        x = opt.rect.right() - reserved + self.GAP
        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        for cls, number in badges:
            colour = opt.palette.highlightedText().color() if selected else QColor(pc.colour(cls))
            top = opt.rect.top() + (opt.rect.height() - self.ICON) // 2
            pixmap = icons.icon(pc.ICONS[cls], colour).pixmap(self.ICON, self.ICON)
            painter.drawPixmap(x, top, pixmap)
            x += self.ICON + 2
            text_width = opt.fontMetrics.horizontalAdvance(str(number))
            painter.save()
            painter.setPen(colour)
            painter.drawText(
                QRect(x, opt.rect.top(), text_width, opt.rect.height()),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                str(number),
            )
            painter.restore()
            x += text_width + self.GAP


class ProjectTree(QTreeWidget):
    """The model tree of the open project. Enter or a double-click opens the node."""

    file_requested = Signal(str)  # a file node: open the file
    field_requested = Signal(str, str)  # a field node: open the file at the field (file, path)
    unit_requested = Signal(str)  # a unit's power modes: open the table editor

    def __init__(self) -> None:
        super().__init__()
        self.setHeaderHidden(True)
        self.setItemDelegate(BadgeDelegate(self))
        self.itemActivated.connect(self._activated)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._context_menu)
        self._top: Node | None = None
        self._nodes: list[Node] = []
        self._items: dict[int, QTreeWidgetItem] = {}
        self._problems: list[Problem] = []

    # ---- activation --------------------------------------------------------------------------
    def _activated(self, item: QTreeWidgetItem, _column: int = 0) -> None:
        kind = item.data(0, KIND_ROLE)
        rel = item.data(0, FILE_ROLE)
        if kind == "unit_modes":
            self.unit_requested.emit(str(item.data(0, UNIT_ROLE)))
        elif kind == "field" and rel:
            self.field_requested.emit(str(rel), str(item.data(0, PATH_ROLE) or ""))
        elif rel:
            self.file_requested.emit(str(rel))

    def activate_current(self) -> None:
        """What Enter does: open the selected node."""
        item = self.currentItem()
        if item is not None:
            self._activated(item)

    def current_unit_id(self) -> str | None:
        item = self.currentItem()
        unit = item.data(0, UNIT_ROLE) if item else None
        return str(unit) if unit else None

    def _context_menu(self, pos: Any) -> None:
        item = self.itemAt(pos)
        if item is None:
            return
        rel = item.data(0, FILE_ROLE)
        unit = item.data(0, UNIT_ROLE)
        menu = QMenu(self)
        edit = (
            menu.addAction(icons.icon("sliders-horizontal"), "Edit power modes…") if unit else None
        )
        open_file = menu.addAction(icons.icon("square-pen"), "Open the file") if rel else None
        if not menu.actions():
            return
        chosen = menu.exec(self.viewport().mapToGlobal(pos))
        if chosen is not None and chosen is edit:
            self.unit_requested.emit(str(unit))
        elif chosen is not None and chosen is open_file:
            self.file_requested.emit(str(rel))

    def request_file(self, rel: str) -> None:
        self.file_requested.emit(rel)

    # ---- content -----------------------------------------------------------------------------
    def file_item_count(self) -> int:
        """How many different files the tree can open."""
        found: set[str] = set()
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                rel = child.data(0, FILE_ROLE)
                if rel and child.data(0, KIND_ROLE) != "unit_modes":
                    found.add(str(rel))
                stack.append(child)
        return len(found)

    def current_file(self) -> str | None:
        item = self.currentItem()
        rel = item.data(0, FILE_ROLE) if item else None
        return str(rel) if rel else None

    def _current_key(self) -> tuple[str, str, str] | None:
        item = self.currentItem()
        if item is None:
            return None
        return (
            str(item.data(0, FILE_ROLE) or ""),
            str(item.data(0, PATH_ROLE) or ""),
            str(item.data(0, KIND_ROLE) or ""),
        )

    def set_project(self, root: Path | None, project: Project | None) -> None:
        selected = self._current_key()
        self.clear()
        self._items = {}
        self._nodes = []
        self._top = None
        if root is None:
            return
        self._top = build_nodes(root, project)
        self._add(self.invisibleRootItem(), self._top)
        self._apply_badges()
        if selected is not None:
            self._select(selected)

    def _add(self, parent: QTreeWidgetItem, node: Node) -> None:
        item = QTreeWidgetItem([node.label])
        item.setData(0, KIND_ROLE, node.kind)
        item.setData(0, NODE_ROLE, len(self._nodes))
        self._nodes.append(node)
        if node.rel:
            item.setData(0, FILE_ROLE, node.rel)
        if node.path:
            item.setData(0, PATH_ROLE, node.path)
        if node.unit_id:
            item.setData(0, UNIT_ROLE, node.unit_id)
        parent.addChild(item)
        self._items[id(node)] = item
        for child in node.children:
            self._add(item, child)
        item.setExpanded(node.expanded)

    def _select(self, key: tuple[str, str, str]) -> None:
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop()
            for i in range(node.childCount()):
                child = node.child(i)
                if (
                    str(child.data(0, FILE_ROLE) or ""),
                    str(child.data(0, PATH_ROLE) or ""),
                    str(child.data(0, KIND_ROLE) or ""),
                ) == key and key[0]:
                    self.setCurrentItem(child)
                    return
                stack.append(child)

    # ---- badges ------------------------------------------------------------------------------
    def set_problems(self, problems: Iterable[Problem]) -> None:
        """Put the problem counts on the nodes (called whenever the problem list changes)."""
        self._problems = list(problems)
        self._apply_badges()

    def _apply_badges(self) -> None:
        if self._top is None:
            return
        counts = badge_counts(self._top, self._problems)
        for node in self._top.walk():
            item = self._items.get(id(node))
            if item is None:
                continue
            by_class = counts.get(id(node), {})
            badges = tuple((c.value, by_class.get(c, 0)) for c in BADGE_CLASSES if by_class.get(c))
            item.setData(0, BADGE_ROLE, badges)
            item.setToolTip(0, self._tooltip(node, by_class))
        self.viewport().update()

    @staticmethod
    def _tooltip(node: Node, by_class: dict[ProblemClass, int]) -> str:
        lines = [node.rel or node.label]
        if node.path:
            lines[0] += f"  ({node.path})"
        shown = [c for c in BADGE_CLASSES if by_class.get(c)]
        if shown:
            lines.append(", ".join(f"{by_class[c]} {pc.LABELS[c].lower()}" for c in shown))
        return "\n".join(lines)

    def current_node(self) -> Node | None:
        """The node of the selected row (None when nothing is selected)."""
        item = self.currentItem()
        index = item.data(0, NODE_ROLE) if item is not None else None
        return self._nodes[int(index)] if index is not None else None

    def problems_of_current(self) -> list[Problem]:
        node = self.current_node()
        return problems_of(node, self._problems) if node is not None else []

    def badges_of(self, item: QTreeWidgetItem) -> dict[ProblemClass, int]:
        """The counts shown on an item (for tests and the Inspector)."""
        raw = item.data(0, BADGE_ROLE) or ()
        return {ProblemClass(c): int(n) for c, n in raw}

    def find_item(
        self, rel: str, path: str = "", kind: str | None = None
    ) -> QTreeWidgetItem | None:
        """The first item that opens `rel` (at `path`); None when there is none."""
        stack = [self.invisibleRootItem()]
        while stack:
            node = stack.pop(0)
            for i in range(node.childCount()):
                child = node.child(i)
                if (
                    child.data(0, FILE_ROLE) == rel
                    and (child.data(0, PATH_ROLE) or "") == path
                    and (kind is None or child.data(0, KIND_ROLE) == kind)
                ):
                    return child
                stack.append(child)
        return None
