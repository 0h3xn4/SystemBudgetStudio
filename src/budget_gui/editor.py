"""YAML text editor with line numbers and jump-to-line (the target of Problems links)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCharFormat,
    QTextFormat,
)
from PySide6.QtWidgets import (
    QMessageBox,
    QPlainTextEdit,
    QTabBar,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from budget_core.io.roundtrip import (
    file_stamp,
    join_text,
    split_text,
    stamp_of,
    write_bytes_atomic,
)
from budget_gui import theme


class FileChangedError(Exception):
    """The file on disk is not the one the editor loaded (someone else changed it)."""


class _Gutter(QWidget):
    def __init__(self, editor: YamlEditor) -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 (Qt naming)
        return QSize(self._editor.gutter_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        self._editor.paint_gutter(event)


class YamlEditor(QPlainTextEdit):
    def __init__(self, path: Path, rel_path: str) -> None:
        super().__init__()
        self.path = path
        self.rel_path = rel_path
        self._stamp: str | None = None  # the file as this editor last read or wrote it
        self._bom = False  # kept when saving
        self._crlf = False
        self.setFont(theme.mono_font(theme.TYPE_SMALL))
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self._gutter = _Gutter(self)
        self.blockCountChanged.connect(self._update_margin)
        self.updateRequest.connect(self._scroll_gutter)
        self._update_margin()
        self.load()

    def load(self) -> None:
        raw = self.path.read_bytes()
        self._stamp = stamp_of(raw)
        try:
            text, self._bom, self._crlf = split_text(raw)
        except UnicodeDecodeError:
            # never show replacement characters: saving them would corrupt the file
            self.setPlainText("# This file is not valid UTF-8 text and cannot be edited here.\n")
            self.setReadOnly(True)
            self.document().setModified(False)
            return
        self.setReadOnly(False)
        self.setPlainText(text)
        self.document().setModified(False)

    def changed_on_disk(self) -> bool:
        """True when the file is no longer the one this editor loaded or wrote last."""
        return file_stamp(self.path) != self._stamp

    def refresh_from_disk(self) -> bool:
        """Reload a file that changed on disk, unless the editor has unsaved edits; the cursor
        stays where it was. Returns True when the text was replaced."""
        if self.document().isModified() or not self.path.is_file() or not self.changed_on_disk():
            return False
        position, scroll = self.textCursor().position(), self.verticalScrollBar().value()
        self.load()
        cursor = self.textCursor()
        cursor.setPosition(min(position, max(self.document().characterCount() - 1, 0)))
        self.setTextCursor(cursor)
        self.verticalScrollBar().setValue(scroll)
        return True

    def save(self, overwrite: bool = False) -> None:
        """Write the text to its file through a temporary file (a crash cannot leave half a
        file), keeping the file's line ends and byte-order mark. Raises `FileChangedError` when
        the file changed on disk since it was loaded, unless `overwrite`; `OutputError` when it
        cannot be written."""
        if self.isReadOnly():
            return
        if not overwrite and self.changed_on_disk():
            raise FileChangedError
        data = join_text(self.toPlainText(), self._bom, self._crlf)
        write_bytes_atomic(self.path, data)
        self._stamp = stamp_of(data)
        self.document().setModified(False)

    def current_line(self) -> int:
        return int(self.textCursor().blockNumber()) + 1

    def goto_line(self, line: int) -> None:
        block = self.document().findBlockByNumber(max(line - 1, 0))
        if not block.isValid():
            block = self.document().lastBlock()
        cursor = self.textCursor()
        cursor.setPosition(block.position())
        self.setTextCursor(cursor)
        self.centerCursor()
        selection = QTextEdit.ExtraSelection()
        highlight = QTextCharFormat()
        highlight.setBackground(QColor(theme.tokens().line_highlight))
        highlight.setProperty(QTextFormat.Property.FullWidthSelection, True)
        selection.format = highlight
        selection.cursor = cursor
        self.setExtraSelections([selection])
        self.setFocus()

    # ---- line number gutter ------------------------------------------------------------------
    def gutter_width(self) -> int:
        digits = len(str(max(1, self.blockCount())))
        return theme.gap(2) + self.fontMetrics().horizontalAdvance("9") * digits

    def _update_margin(self) -> None:
        self.setViewportMargins(self.gutter_width(), 0, 0, 0)

    def _scroll_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_margin()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        area = self.contentsRect()
        self._gutter.setGeometry(QRect(area.left(), area.top(), self.gutter_width(), area.height()))

    def paint_gutter(self, event: QPaintEvent) -> None:
        painter = QPainter(self._gutter)
        tokens = theme.tokens()
        painter.fillRect(event.rect(), QColor(tokens.gutter_bg))
        painter.setPen(QColor(tokens.gutter_text))
        block = self.firstVisibleBlock()
        number = block.blockNumber()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        bottom = top + round(self.blockBoundingRect(block).height())
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.drawText(
                    0,
                    top,
                    self._gutter.width() - theme.gap(1),
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + round(self.blockBoundingRect(block).height())
            number += 1


class EditorTabs(QTabWidget):
    """Workspace tabs: fixed tabs (the budget view) plus one closable tab per open file."""

    dirty_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setTabsClosable(True)
        self.tabCloseRequested.connect(self._close_tab)
        self._editors: dict[str, YamlEditor] = {}
        self._modifiable: list[Any] = []  # fixed widgets with is_modified() and discard_changes()

    def add_fixed(self, widget: QWidget, title: str) -> None:
        index = self.addTab(widget, title)
        bar = self.tabBar()
        if bar is not None:  # the budget view cannot be closed: hide its close button
            button = bar.tabButton(index, QTabBar.ButtonPosition.RightSide)
            if button is not None:
                button.hide()

    def current_editor(self) -> YamlEditor | None:
        widget = self.currentWidget()
        return widget if isinstance(widget, YamlEditor) else None

    def open_file(self, root: Path, rel: str, line: int | None = None) -> YamlEditor:
        editor = self._editors.get(rel)
        if editor is None:
            editor = YamlEditor(root / rel, rel)
            editor.document().modificationChanged.connect(lambda _m, e=editor: self._retitle(e))
            self._editors[rel] = editor
            self.addTab(editor, Path(rel).name)
            self.setTabToolTip(self.indexOf(editor), rel)
        self.setCurrentWidget(editor)
        if line is not None:
            editor.goto_line(line)
        return editor

    def _retitle(self, editor: YamlEditor) -> None:
        index = self.indexOf(editor)
        if index >= 0:
            name = Path(editor.rel_path).name
            self.setTabText(index, name + ("*" if editor.document().isModified() else ""))
        self.dirty_changed.emit()

    def _close_tab(self, index: int) -> None:
        widget = self.widget(index)
        if not isinstance(widget, YamlEditor):
            return  # the grids and the scenario are fixed tabs
        if widget.document().isModified() and not self.confirm_discard(
            "This file has unsaved changes."
        ):
            return
        self._editors.pop(widget.rel_path, None)
        self.removeTab(index)
        widget.deleteLater()

    def confirm_discard(self, reason: str) -> bool:
        """Ask whether unsaved edits may be thrown away; False keeps them."""
        answer = QMessageBox.question(
            self,
            "System Budget Studio",
            f"{reason} Discard the changes?",
            QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
        )
        return answer == QMessageBox.StandardButton.Discard

    def register_modifiable(self, widget: Any) -> None:
        self._modifiable.append(widget)

    def has_unsaved_changes(self) -> bool:
        return any(e.document().isModified() for e in self._editors.values()) or any(
            w.is_modified() for w in self._modifiable
        )

    def discard_all_changes(self) -> None:
        """Forget unsaved edits (after the user chose 'close without saving')."""
        for editor in self._editors.values():
            editor.document().setModified(False)
        for widget in self._modifiable:
            widget.discard_changes()

    def close_all_files(self) -> None:
        for rel in list(self._editors):
            self._close_tab(self.indexOf(self._editors[rel]))

    def reload_clean_files(self) -> None:
        """After a project reload, refresh the text editors that have no unsaved edits and whose
        file changed; an editor whose file is as it left it is not touched (cursor and undo
        history stay). The grids follow the project through their own document."""
        for editor in self._editors.values():
            editor.refresh_from_disk()
