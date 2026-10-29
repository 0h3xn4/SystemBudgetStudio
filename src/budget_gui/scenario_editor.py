"""The scenario editor: rules and segments as sentences, edited through the shared document (D-160).

A rule is one sentence you can change in place: "[Downlink] [during every pass over] [gs_north],
from [30] s before to [0] s after". Its parts are the controls, so there is no separate builder
dialog. The order of the rules matters (a later rule wins), so each row can move up and down. A
segment reads "[Imaging] from T+[100] s for [300] s".

The editor holds no data of its own: it shows the scenario of the `ModelDocument` and every change
is an edit of that document, one undo step, saved with the same Save as the grids. The model
checks each edit; what is wrong is said in words under the editor, never with a message box.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from budget_core.model_choices import REGISTRY, ModelChoice, source_of
from budget_gui import theme
from budget_gui.components import Button, icon_button
from budget_gui.edit_bar import EditBar
from budget_gui.model_document import ModelDocument, set_at

RULE_KINDS = ("during_pass", "in_eclipse", "in_sunlight")
SHADOW_MODELS = ("cylindrical", "conical")
# the model choices made in the scenario file, from the registry (D-219): the field is also the
# name of the control
CHOICE_FIELDS = ("shadow_model", "earth_model", "irradiance_model")
WHEN = {
    "during_pass": "during every pass over",
    "in_eclipse": "while in eclipse",
    "in_sunlight": "while in sunlight",
}
MAX_SECONDS = 10_000_000.0


def _seconds(value: object) -> str:
    return f"{value:g}" if isinstance(value, int | float) else "?"


def _capital(text: str) -> str:
    return text[:1].upper() + text[1:]


def rule_sentence(rule: Mapping[str, Any]) -> str:
    """A rule in words: 'Downlink during every pass over gs_north, from 30 s before to 0 s after'
    (the timing only when there is some)."""
    kind = str(rule.get("kind", ""))
    mode = str(rule.get("mode") or "?")
    text = f"{_capital(mode)} {WHEN.get(kind, kind)}"
    if kind == "during_pass":
        text += f" {rule.get('site') or '…'}"
        lead, lag = rule.get("lead_s", 0.0), rule.get("lag_s", 0.0)
        if lead or lag:
            text += f", from {_seconds(lead)} s before to {_seconds(lag)} s after"
    return text


def segment_sentence(segment: Mapping[str, Any]) -> str:
    """A manual segment in words: 'Imaging from T+100 s for 300 s'."""
    mode = str(segment.get("mode") or "?")
    start, duration = segment.get("start_s"), segment.get("duration_s")
    return f"{_capital(mode)} from T+{_seconds(start)} s for {_seconds(duration)} s"


def _combo(items: list[str]) -> QComboBox:
    box = QComboBox()
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    box.addItems(items)
    return box


def _spin(maximum: float = MAX_SECONDS) -> QDoubleSpinBox:
    box = QDoubleSpinBox()
    box.setDecimals(1)
    box.setRange(0.0, maximum)
    box.setSuffix(" s")
    box.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
    box.setKeyboardTracking(False)
    box.setMaximumWidth(theme.px(theme.COMBO_MAX_WIDTH))
    return box


def _set_combo(box: QComboBox, text: str) -> None:
    """Show `text` even when it is not among the items (a mode or site the project lost)."""
    if text and box.findText(text) < 0:
        box.addItem(text)
    box.setCurrentText(text)


class _Row(QFrame):
    """One rule or segment: a number, the sentence's controls, and the icons that move it up or
    down or remove it (each has a tooltip and a name for screen readers)."""

    def __init__(self, number: int) -> None:
        super().__init__()
        self.setProperty("role", "card")
        self.number = QLabel(f"{number}.")
        self.sentence = QHBoxLayout()
        self.sentence.addWidget(self.number)
        self.up = icon_button("chevron-up", "Move up: a later rule wins over an earlier one")
        self.down = icon_button("chevron-down", "Move down: a later rule wins over an earlier one")
        self.remove = icon_button("trash-2", "Remove (Undo brings it back)")
        buttons = QHBoxLayout()
        for button in (self.up, self.down, self.remove):
            buttons.addWidget(button)
        top = QHBoxLayout()
        top.addLayout(self.sentence, 1)
        top.addLayout(buttons)
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(*theme.inset(1, 0))
        self.layout_.addLayout(top)


class _RuleRow(_Row):
    def __init__(self, number: int, modes: list[str], sites: list[str]) -> None:
        super().__init__(number)
        self.mode = _combo(modes)
        self.when = _combo([WHEN[k] for k in RULE_KINDS])
        self.site = _combo(sites)
        self.lead = _spin()
        self.lag = _spin()
        for widget, name in (
            (self.mode, "Mode of the rule"),
            (self.when, "When the rule applies"),
            (self.site, "Site of the rule"),
            (self.lead, "Seconds before the pass"),
            (self.lag, "Seconds after the pass"),
        ):
            widget.setAccessibleName(name)
        for widget in (self.mode, self.when, self.site):
            self.sentence.addWidget(widget)
        self.sentence.addStretch(1)
        self.timing = QWidget()
        timing = QHBoxLayout(self.timing)
        timing.setContentsMargins(theme.gap(4), 0, 0, 0)
        for part in (
            QLabel("Start it"),
            self.lead,
            QLabel("before the pass and keep it"),
            self.lag,
            QLabel("after it"),
        ):
            timing.addWidget(part)
        timing.addStretch(1)
        self.layout_.addWidget(self.timing)


class _SegmentRow(_Row):
    def __init__(self, number: int, modes: list[str]) -> None:
        super().__init__(number)
        self.mode = _combo(modes)
        self.start = _spin()
        self.duration = _spin()
        for widget, name in (
            (self.mode, "Mode of the segment"),
            (self.start, "Start of the segment, seconds after the scenario start"),
            (self.duration, "Duration of the segment in seconds"),
        ):
            widget.setAccessibleName(name)
        for part in (self.mode, QLabel("from T+"), self.start, QLabel("for"), self.duration):
            self.sentence.addWidget(part)
        self.sentence.addStretch(1)
        for button, tip in (
            (self.up, "Move up (the order does not change the result)"),
            (self.down, "Move down (the order does not change the result)"),
        ):
            button.set_tip(tip)
            button.setAccessibleName(tip)


def _entry_of(field: str) -> ModelChoice:
    return next(m for m in REGISTRY if m.scope == "scenario" and m.field == field)


def _declare_model_choices(data: dict[str, Any]) -> None:
    requires = list(data.get("requires") or [])
    if "model_choices" not in requires:
        requires.append("model_choices")
    data["requires"] = requires


class ScenarioEditor(QWidget):
    """Default mode, shadow model, sites, rules and manual segments of one scenario."""

    def __init__(self, document: ModelDocument) -> None:
        super().__init__()
        self.document = document
        self._root: Path | None = None
        self._id = ""
        self._modes: list[str] = []
        self._sites: list[str] = []
        self._built: tuple[Any, ...] = ()
        self._loading = False
        self.rule_rows: list[_RuleRow] = []
        self.segment_rows: list[_SegmentRow] = []

        self.default_mode = QComboBox()
        self.default_mode.setAccessibleName("Default mode")
        self.choice_combos: dict[str, QComboBox] = {}
        for field in CHOICE_FIELDS:
            entry = _entry_of(field)
            combo = QComboBox()
            combo.setAccessibleName(entry.title)
            combo.setToolTip(f"{entry.title}: {entry.acts_on} ({entry.reference})")
            for choice in entry.choices:
                combo.addItem(choice.id)
                combo.setItemData(
                    combo.count() - 1,
                    " ".join(
                        part
                        for part in (choice.title + ".", choice.note, source_of(choice))
                        if part
                    ),
                    Qt.ItemDataRole.ToolTipRole,
                )
            self.choice_combos[field] = combo
        self.shadow_model = self.choice_combos["shadow_model"]
        self.earth_model = self.choice_combos["earth_model"]
        self.irradiance_model = self.choice_combos["irradiance_model"]
        self.sites_list = QListWidget()
        self.sites_list.setMaximumHeight(theme.px(theme.SITES_MAX_HEIGHT))
        form = QFormLayout()
        form.addRow("Default mode", self.default_mode)
        for field in CHOICE_FIELDS:
            form.addRow(_entry_of(field).title, self.choice_combos[field])
        form.addRow("Sites", self.sites_list)

        self.rules_title = QLabel("Rules: in this order, a later rule wins")
        self.rules_title.setProperty("role", "section-title")
        self.rules_box = QVBoxLayout()
        self.add_rule_button = Button("Add rule", icon="plus", compact=True)
        self.segments_title = QLabel(
            "Manual segments: applied last (Shift+drag on the timeline adds one)"
        )
        self.segments_title.setProperty("role", "section-title")
        self.segments_box = QVBoxLayout()
        self.add_segment_button = Button("Add segment", icon="plus", compact=True)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setProperty("role", "error")
        self.note_label = QLabel()
        self.note_label.setWordWrap(True)
        self.bar = EditBar(document, legend=False)

        layout = QVBoxLayout(self)
        bar_row = QHBoxLayout()
        bar_row.addStretch(1)
        bar_row.addWidget(self.bar)  # at the top: Save stays in view when the editor scrolls
        layout.addLayout(bar_row)
        layout.addLayout(form)
        layout.addWidget(self.rules_title)
        layout.addLayout(self.rules_box)
        add_rule = QHBoxLayout()
        add_rule.addWidget(self.add_rule_button)
        add_rule.addStretch(1)
        layout.addLayout(add_rule)
        layout.addWidget(self.segments_title)
        layout.addLayout(self.segments_box)
        add_segment = QHBoxLayout()
        add_segment.addWidget(self.add_segment_button)
        add_segment.addStretch(1)
        layout.addLayout(add_segment)
        layout.addWidget(self.error_label)
        layout.addWidget(self.note_label)
        layout.addStretch(1)
        self.save_requested = self.bar.save_requested

        self.add_rule_button.clicked.connect(lambda: self.add_rule())
        self.add_segment_button.clicked.connect(lambda: self.add_segment())
        self.default_mode.currentTextChanged.connect(self._default_mode_changed)
        for field, combo in self.choice_combos.items():
            combo.currentTextChanged.connect(lambda text, f=field: self._choice_changed(f, text))
        self.sites_list.itemChanged.connect(self._sites_changed)
        document.changed.connect(self._sync)

    # ---- which scenario ----------------------------------------------------------------------
    @property
    def root(self) -> Path | None:
        """The project folder the scenario belongs to."""
        return self._root

    @property
    def scenario_id(self) -> str:
        return self._id

    def _rel(self) -> str | None:
        rel = f"scenarios/{self._id}.yaml"
        return rel if self._id and self.document.has(rel) else None

    def show_scenario(
        self, root: Path, scenario_id: str, modes: list[str], sites: list[str]
    ) -> None:
        self._root, self._id = root, scenario_id
        self._modes, self._sites = sorted(modes), sorted(sites)
        self._sync()

    def clear(self) -> None:
        self._id = ""
        self._sync()

    def is_modified(self) -> bool:
        rel = f"scenarios/{self._id}.yaml"
        return rel in self.document.modified_files()

    # ---- showing the document ----------------------------------------------------------------
    def _data(self) -> dict[str, Any] | None:
        rel = self._rel()
        return self.document.data(rel) if rel is not None else None

    def _sync(self) -> None:
        data = self._data()
        if data is None:
            self._clear_rows()
            self.error_label.setText("")
            return
        rules = [r for r in data.get("rules") or [] if isinstance(r, dict)]
        segments = [s for s in data.get("segments") or [] if isinstance(s, dict)]
        signature = (self._id, tuple(self._modes), tuple(self._sites), len(rules), len(segments))
        self._loading = True
        try:
            if signature != self._built:
                self._build(len(rules), len(segments))
                self._built = signature
            self._show_values(data, rules, segments)
        finally:
            self._loading = False
        self._show_problems()

    def _clear_rows(self) -> None:
        for rows, box in ((self.rule_rows, self.rules_box), (self.segment_rows, self.segments_box)):
            for row in rows:
                box.removeWidget(row)
                row.deleteLater()
            rows.clear()
        self._built = ()
        self.default_mode.clear()
        self.sites_list.clear()

    def _build(self, rule_count: int, segment_count: int) -> None:
        self._clear_rows()
        for index in range(rule_count):
            row = _RuleRow(index + 1, self._modes, self._sites)
            self._wire_rule(row, index)
            self.rules_box.addWidget(row)
            self.rule_rows.append(row)
        for index in range(segment_count):
            seg = _SegmentRow(index + 1, self._modes)
            self._wire_segment(seg, index)
            self.segments_box.addWidget(seg)
            self.segment_rows.append(seg)
        self.default_mode.addItems(self._modes)
        self.sites_list.clear()
        for site in self._sites:
            item = QListWidgetItem(site)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.sites_list.addItem(item)

    def _show_values(
        self, data: dict[str, Any], rules: list[dict[str, Any]], segments: list[dict[str, Any]]
    ) -> None:
        _set_combo(self.default_mode, str(data.get("default_mode") or ""))
        for field, combo in self.choice_combos.items():
            combo.setCurrentText(str(data.get(field) or _entry_of(field).default))
        chosen = set(data.get("sites") or [])
        for index in range(self.sites_list.count()):
            item = self.sites_list.item(index)
            state = Qt.CheckState.Checked if item.text() in chosen else Qt.CheckState.Unchecked
            if item.checkState() != state:
                item.setCheckState(state)
        for index, (row, rule) in enumerate(zip(self.rule_rows, rules, strict=True)):
            kind = str(rule.get("kind") or RULE_KINDS[0])
            _set_combo(row.mode, str(rule.get("mode") or ""))
            row.when.setCurrentIndex(RULE_KINDS.index(kind) if kind in RULE_KINDS else 0)
            _set_combo(row.site, str(rule.get("site") or ""))
            passes = kind == "during_pass"
            row.site.setVisible(passes)
            row.timing.setVisible(passes)
            row.lead.setValue(float(rule.get("lead_s") or 0.0))
            row.lag.setValue(float(rule.get("lag_s") or 0.0))
            row.up.setEnabled(index > 0)
            row.down.setEnabled(index < len(rules) - 1)
            sentence = rule_sentence(rule)
            row.setAccessibleName(sentence)
            row.setToolTip(sentence)
        for index, (seg, segment) in enumerate(zip(self.segment_rows, segments, strict=True)):
            _set_combo(seg.mode, str(segment.get("mode") or ""))
            seg.start.setValue(float(segment.get("start_s") or 0.0))
            seg.duration.setValue(float(segment.get("duration_s") or 0.0))
            seg.up.setEnabled(index > 0)
            seg.down.setEnabled(index < len(segments) - 1)
            sentence = segment_sentence(segment)
            seg.setAccessibleName(sentence)
            seg.setToolTip(sentence)

    def _show_problems(self) -> None:
        rel = self._rel()
        lines = []
        for problem in self.document.problems(rel) if rel else []:
            lines.append(
                f"{problem.path or 'scenario'}: {problem.message}"
                + (f" {problem.hint}" if problem.hint else "")
            )
        self.error_label.setText("\n".join(lines))
        self.error_label.setVisible(bool(lines))

    # ---- making edits ------------------------------------------------------------------------
    def _edit(self, change: Callable[[dict[str, Any]], None], text: str) -> bool:
        rel = self._rel()
        if rel is None or self._loading:
            return False
        return self.document.edit([(rel, change)], f"Edit scenario {self._id}: {text}")

    def _default_mode_changed(self, text: str) -> None:
        if text:
            self._edit(lambda data: set_at(data, ("default_mode",), text), "default mode")

    def _choice_changed(self, field: str, text: str) -> None:
        """A model choice: the value is written (a choice at its default is left out of the file),
        and a non-default one of a model that older versions do not know also declares the
        feature in project.yaml, in the same undo step (D-219)."""
        rel = self._rel()
        if rel is None or self._loading or not text:
            return
        entry = _entry_of(field)
        value = None if text == entry.default else text

        def change(data: dict[str, Any]) -> None:
            set_at(data, (field,), value)

        changes: list[tuple[str, Callable[[dict[str, Any]], None]]] = [(rel, change)]
        has_project = self.document.has("project.yaml")
        requires = (self.document.data("project.yaml").get("requires") or []) if has_project else []
        if (
            value is not None
            and field != "shadow_model"
            and has_project
            and ("model_choices" not in requires)
        ):
            changes.append(("project.yaml", _declare_model_choices))
        self.document.edit(changes, f"Edit scenario {self._id}: {entry.label}")

    def _sites_changed(self, _item: QListWidgetItem) -> None:
        checked = {
            self.sites_list.item(i).text()
            for i in range(self.sites_list.count())
            if self.sites_list.item(i).checkState() == Qt.CheckState.Checked
        }

        def apply(data: dict[str, Any]) -> None:
            current = list(data.get("sites") or [])
            data["sites"] = [s for s in current if s in checked] + sorted(checked - set(current))

        self._edit(apply, "sites")

    # rules
    def rule_count(self) -> int:
        return len(self.rule_rows)

    def rule_text(self, row: int) -> str:
        data = self._data() or {}
        return rule_sentence((data.get("rules") or [])[row])

    def _wire_rule(self, row: _RuleRow, index: int) -> None:
        row.mode.currentTextChanged.connect(lambda text: self.set_rule(index, mode=text))
        row.site.currentTextChanged.connect(lambda text: self.set_rule(index, site=text))
        row.when.currentIndexChanged.connect(lambda i: self.set_rule(index, kind=RULE_KINDS[i]))
        row.lead.editingFinished.connect(lambda: self.set_rule(index, lead_s=row.lead.value()))
        row.lag.editingFinished.connect(lambda: self.set_rule(index, lag_s=row.lag.value()))
        row.up.clicked.connect(lambda: self.move_rule(index, -1))
        row.down.clicked.connect(lambda: self.move_rule(index, 1))
        row.remove.clicked.connect(lambda: self.remove_rule(index))

    def add_rule(self) -> bool:
        data = self._data() or {}
        mode = str(data.get("default_mode") or (self._modes[0] if self._modes else ""))
        listed = list(data.get("sites") or [])
        site = listed[0] if listed else (self._sites[0] if self._sites else "")
        rule: dict[str, Any] = {"kind": "during_pass", "mode": mode, "lead_s": 0.0, "lag_s": 0.0}
        if site:
            rule["site"] = site
        return self._edit(lambda d: d.setdefault("rules", []).append(rule), "add a rule")

    def remove_rule(self, row: int) -> bool:
        if not 0 <= row < self.rule_count():
            return False
        return self._edit(lambda d: d["rules"].__delitem__(row), f"remove rule {row + 1}")

    def move_rule(self, row: int, delta: int) -> bool:
        target = row + delta
        if not (0 <= row < self.rule_count() and 0 <= target < self.rule_count()):
            return False

        def apply(data: dict[str, Any]) -> None:
            rules = data["rules"]
            rules[row], rules[target] = rules[target], rules[row]

        return self._edit(apply, f"move rule {row + 1} {'up' if delta < 0 else 'down'}")

    def set_rule(
        self,
        row: int,
        kind: str | None = None,
        site: str | None = None,
        mode: str | None = None,
        lead_s: float | None = None,
        lag_s: float | None = None,
    ) -> bool:
        """Change parts of one rule in one undo step. Changing the kind keeps the rule valid: a
        pass rule gets a site, the others lose their site, lead and lag."""
        if not 0 <= row < self.rule_count() or self._loading:
            return False

        def apply(data: dict[str, Any]) -> None:
            rule = data["rules"][row]
            if kind is not None:
                rule["kind"] = kind
                if kind != "during_pass":
                    for key in ("site", "lead_s", "lag_s"):
                        rule.pop(key, None)
                elif not rule.get("site"):
                    listed = data.get("sites") or []
                    if listed or self._sites:
                        rule["site"] = (listed or self._sites)[0]
            if site is not None:
                if site:
                    rule["site"] = site
                else:
                    rule.pop("site", None)
            if mode is not None:
                rule["mode"] = mode
            for key, number in (("lead_s", lead_s), ("lag_s", lag_s)):
                if number is not None:
                    rule[key] = number

        return self._edit(apply, f"rule {row + 1}")

    # segments
    def segment_count(self) -> int:
        return len(self.segment_rows)

    def _wire_segment(self, seg: _SegmentRow, index: int) -> None:
        seg.mode.currentTextChanged.connect(lambda text: self.set_segment(index, mode=text))
        seg.start.editingFinished.connect(lambda: self.set_segment(index, start=seg.start.value()))
        seg.duration.editingFinished.connect(
            lambda: self.set_segment(index, duration=seg.duration.value())
        )
        seg.up.clicked.connect(lambda: self.move_segment(index, -1))
        seg.down.clicked.connect(lambda: self.move_segment(index, 1))
        seg.remove.clicked.connect(lambda: self.remove_segment(index))

    def add_segment(self, start: float = 0.0, duration: float = 60.0) -> bool:
        data = self._data() or {}
        mode = str(data.get("default_mode") or (self._modes[0] if self._modes else ""))
        segment = {"start_s": start, "duration_s": duration, "mode": mode}
        return self._edit(lambda d: d.setdefault("segments", []).append(segment), "add a segment")

    def remove_segment(self, row: int) -> bool:
        if not 0 <= row < self.segment_count():
            return False
        return self._edit(lambda d: d["segments"].__delitem__(row), f"remove segment {row + 1}")

    def move_segment(self, row: int, delta: int) -> bool:
        target = row + delta
        if not (0 <= row < self.segment_count() and 0 <= target < self.segment_count()):
            return False

        def apply(data: dict[str, Any]) -> None:
            segments = data["segments"]
            segments[row], segments[target] = segments[target], segments[row]

        return self._edit(apply, f"move segment {row + 1} {'up' if delta < 0 else 'down'}")

    def set_segment(
        self,
        row: int,
        start: float | None = None,
        duration: float | None = None,
        mode: str | None = None,
    ) -> bool:
        if not 0 <= row < self.segment_count() or self._loading:
            return False

        def apply(data: dict[str, Any]) -> None:
            segment = data["segments"][row]
            for key, value in (("start_s", start), ("duration_s", duration), ("mode", mode)):
                if value is not None:
                    segment[key] = value

        return self._edit(apply, f"segment {row + 1}")

    def segment(self, row: int) -> tuple[float, float, str]:
        seg = ((self._data() or {}).get("segments") or [])[row]
        return float(seg["start_s"]), float(seg["duration_s"]), str(seg["mode"])

    # ---- saving ------------------------------------------------------------------------------
    def save(self) -> bool:
        """Write the changed files (the same Save as the grids): see `ModelDocument.save`."""
        report = self.document.save()
        self.note_label.setText("" if report.ok else report.message)
        return report.ok
