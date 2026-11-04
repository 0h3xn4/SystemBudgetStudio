"""Pointing and manoeuvres in the scenario editor (2.3.0, D-235).

The default pointing mode, the pointing rules (the same kinds as the mode rules, but their mode is
a pointing mode of `config/pointing.yaml`) and the burns of `config/propulsion.yaml` the scenario
places. Every change is one undo step on the scenario file, like the rest of the editor.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from budget_gui import theme
from budget_gui.components import Button
from budget_gui.model_document import ModelDocument
from budget_gui.scenario_editor import (
    RULE_KINDS,
    _combo,
    _Row,
    _RuleRow,
    _set_combo,
    _spin,
    rule_sentence,
)

NONE_TEXT = "(none)"


class _ManeuverRow(_Row):
    def __init__(self, number: int, names: list[str]) -> None:
        super().__init__(number)
        self.name = _combo(names)
        self.start = _spin()
        self.name.setAccessibleName("Manoeuvre")
        self.start.setAccessibleName("Start of the burn, seconds after the scenario start")
        self.name.setToolTip(
            "A manoeuvre of config/propulsion.yaml; its burn time comes from there"
        )
        for part in (self.name, QLabel("starts at T+"), self.start):
            self.sentence.addWidget(part)
        self.sentence.addStretch(1)
        self.up.hide()
        self.down.hide()


class ScenarioOpsEditor(QWidget):
    """Edits `pointing_default`, `pointing_rules` and `maneuvers` of the shown scenario."""

    def __init__(self, document: ModelDocument) -> None:
        super().__init__()
        self.document = document
        self._id = ""
        self._sites: list[str] = []
        self.pointing_modes: list[str] = []
        self.maneuver_names: list[str] = []
        self._built: tuple[Any, ...] = ()
        self._loading = False
        self.rule_rows: list[_RuleRow] = []
        self.maneuver_rows: list[_ManeuverRow] = []

        self.title = QLabel("Pointing: separate from the spacecraft modes, costs the slews")
        self.title.setProperty("role", "section-title")
        self.default_combo = QComboBox()
        self.default_combo.setAccessibleName("Default pointing mode")
        self.default_combo.setToolTip(
            "The pointing mode that holds over the whole scenario unless a rule changes it. Each "
            "change costs the slew between the two modes (config/pointing.yaml)."
        )
        form = QFormLayout()
        form.addRow("Default pointing mode", self.default_combo)
        self.rules_box = QVBoxLayout()
        self.add_rule_button = Button("Add pointing rule", icon="plus", compact=True)
        self.maneuvers_title = QLabel("Manoeuvres: burns placed in the scenario")
        self.maneuvers_title.setProperty("role", "section-title")
        self.maneuvers_box = QVBoxLayout()
        self.add_maneuver_button = Button("Add manoeuvre", icon="plus", compact=True)
        self.note = QLabel()
        self.note.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, theme.gap(2), 0, 0)
        layout.addWidget(self.title)
        layout.addLayout(form)
        layout.addLayout(self.rules_box)
        add_rule = QHBoxLayout()
        add_rule.addWidget(self.add_rule_button)
        add_rule.addStretch(1)
        layout.addLayout(add_rule)
        layout.addWidget(self.maneuvers_title)
        layout.addLayout(self.maneuvers_box)
        add_maneuver = QHBoxLayout()
        add_maneuver.addWidget(self.add_maneuver_button)
        add_maneuver.addStretch(1)
        layout.addLayout(add_maneuver)
        layout.addWidget(self.note)

        self.add_rule_button.clicked.connect(lambda: self.add_rule())
        self.add_maneuver_button.clicked.connect(lambda: self.add_maneuver())
        self.default_combo.currentTextChanged.connect(self._default_changed)
        document.changed.connect(self._sync)

    # ---- which scenario ----------------------------------------------------------------------
    def show_scenario(
        self,
        scenario_id: str,
        sites: list[str],
        pointing_modes: list[str],
        maneuver_names: list[str],
    ) -> None:
        self._id = scenario_id
        self._sites = sorted(sites)
        self.pointing_modes = sorted(pointing_modes)
        self.maneuver_names = sorted(maneuver_names)
        self._sync()

    def clear(self) -> None:
        self._id = ""
        self._sync()

    def _rel(self) -> str | None:
        rel = f"scenarios/{self._id}.yaml"
        return rel if self._id and self.document.has(rel) else None

    def _data(self) -> dict[str, Any] | None:
        rel = self._rel()
        return self.document.data(rel) if rel is not None else None

    # ---- showing the document ----------------------------------------------------------------
    def _sync(self) -> None:
        data = self._data()
        if data is None:
            self._clear_rows()
            return
        rules = [r for r in data.get("pointing_rules") or [] if isinstance(r, dict)]
        burns = [m for m in data.get("maneuvers") or [] if isinstance(m, dict)]
        signature = (
            self._id,
            tuple(self.pointing_modes),
            tuple(self.maneuver_names),
            tuple(self._sites),
            len(rules),
            len(burns),
        )
        self._loading = True
        try:
            if signature != self._built:
                self._build(len(rules), len(burns))
                self._built = signature
            self._show_values(data, rules, burns)
        finally:
            self._loading = False

    def _clear_rows(self) -> None:
        for rows, box in (
            (self.rule_rows, self.rules_box),
            (self.maneuver_rows, self.maneuvers_box),
        ):
            for row in rows:
                box.removeWidget(row)
                row.deleteLater()
            rows.clear()
        self._built = ()
        self.default_combo.clear()

    def _build(self, rule_count: int, burn_count: int) -> None:
        self._clear_rows()
        for index in range(rule_count):
            row = _RuleRow(index + 1, self.pointing_modes, self._sites)
            row.mode.setToolTip("The pointing mode that holds while the rule applies")
            row.mode.setAccessibleName("Pointing mode of the rule")
            row.up.set_tip("Move up: a later rule wins over an earlier one")
            row.down.set_tip("Move down: a later rule wins over an earlier one")
            self._wire_rule(row, index)
            self.rules_box.addWidget(row)
            self.rule_rows.append(row)
        for index in range(burn_count):
            burn = _ManeuverRow(index + 1, self.maneuver_names)
            burn.name.currentTextChanged.connect(
                lambda text, i=index: self.set_maneuver(i, name=text)
            )
            burn.start.editingFinished.connect(
                lambda i=index, b=burn: self.set_maneuver(i, start_s=b.start.value())
            )
            burn.remove.clicked.connect(lambda _=False, i=index: self.remove_maneuver(i))
            self.maneuvers_box.addWidget(burn)
            self.maneuver_rows.append(burn)
        self.default_combo.addItem(NONE_TEXT)
        self.default_combo.addItems(self.pointing_modes)

    def _show_values(
        self, data: dict[str, Any], rules: list[dict[str, Any]], burns: list[dict[str, Any]]
    ) -> None:
        _set_combo(self.default_combo, str(data.get("pointing_default") or NONE_TEXT))
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
            row.setAccessibleName("Pointing: " + rule_sentence(rule))
        for burn_row, burn in zip(self.maneuver_rows, burns, strict=True):
            _set_combo(burn_row.name, str(burn.get("name") or ""))
            burn_row.start.setValue(float(burn.get("start_s") or 0.0))
        has_modes, has_burns = bool(self.pointing_modes), bool(self.maneuver_names)
        self.default_combo.setEnabled(has_modes)
        self.add_rule_button.setEnabled(has_modes and bool(data.get("pointing_default")))
        self.add_maneuver_button.setEnabled(has_burns)
        notes = []
        if not has_modes:
            notes.append("No pointing modes: add config/pointing.yaml to use pointing.")
        if not has_burns:
            notes.append("No manoeuvres: add config/propulsion.yaml to place burns.")
        self.note.setText(" ".join(notes))
        self.note.setVisible(bool(notes))

    # ---- making edits ------------------------------------------------------------------------
    def _edit(self, change: Callable[[dict[str, Any]], None], text: str) -> bool:
        rel = self._rel()
        if rel is None or self._loading:
            return False
        return self.document.edit([(rel, change)], f"Edit scenario {self._id}: {text}")

    def _default_changed(self, text: str) -> None:
        if self._loading:
            return
        self.set_default("" if text == NONE_TEXT else text)

    def set_default(self, mode: str) -> bool:
        def apply(data: dict[str, Any]) -> None:
            if mode:
                data["pointing_default"] = mode
            else:
                data.pop("pointing_default", None)
                data.pop("pointing_rules", None)

        return self._edit(apply, "default pointing mode")

    def rule_count(self) -> int:
        return len(self.rule_rows)

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
        mode = str(data.get("pointing_default") or (self.pointing_modes or [""])[0])
        listed = list(data.get("sites") or [])
        site = listed[0] if listed else (self._sites[0] if self._sites else "")
        rule: dict[str, Any] = {"kind": "during_pass", "mode": mode, "lead_s": 0.0, "lag_s": 0.0}
        if site:
            rule["site"] = site
        return self._edit(
            lambda d: d.setdefault("pointing_rules", []).append(rule), "add a pointing rule"
        )

    def remove_rule(self, row: int) -> bool:
        if not 0 <= row < self.rule_count():
            return False

        def apply(data: dict[str, Any]) -> None:
            data["pointing_rules"].__delitem__(row)
            if not data["pointing_rules"]:
                del data["pointing_rules"]

        return self._edit(apply, f"remove pointing rule {row + 1}")

    def move_rule(self, row: int, delta: int) -> bool:
        target = row + delta
        if not (0 <= row < self.rule_count() and 0 <= target < self.rule_count()):
            return False

        def apply(data: dict[str, Any]) -> None:
            rules = data["pointing_rules"]
            rules[row], rules[target] = rules[target], rules[row]

        return self._edit(apply, f"move pointing rule {row + 1}")

    def set_rule(
        self,
        row: int,
        kind: str | None = None,
        site: str | None = None,
        mode: str | None = None,
        lead_s: float | None = None,
        lag_s: float | None = None,
    ) -> bool:
        if not 0 <= row < self.rule_count() or self._loading:
            return False

        def apply(data: dict[str, Any]) -> None:
            rule = data["pointing_rules"][row]
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

        return self._edit(apply, f"pointing rule {row + 1}")

    # manoeuvres
    def maneuver_count(self) -> int:
        return len(self.maneuver_rows)

    def add_maneuver(self) -> bool:
        if not self.maneuver_names:
            return False
        placed = {"name": self.maneuver_names[0], "start_s": 0.0}
        return self._edit(lambda d: d.setdefault("maneuvers", []).append(placed), "add a manoeuvre")

    def remove_maneuver(self, row: int) -> bool:
        if not 0 <= row < self.maneuver_count():
            return False

        def apply(data: dict[str, Any]) -> None:
            data["maneuvers"].__delitem__(row)
            if not data["maneuvers"]:
                del data["maneuvers"]

        return self._edit(apply, f"remove manoeuvre {row + 1}")

    def set_maneuver(self, row: int, name: str | None = None, start_s: float | None = None) -> bool:
        if not 0 <= row < self.maneuver_count() or self._loading:
            return False

        def apply(data: dict[str, Any]) -> None:
            burn = data["maneuvers"][row]
            if name is not None:
                burn["name"] = name
            if start_s is not None:
                burn["start_s"] = start_s

        return self._edit(apply, f"manoeuvre {row + 1}")
