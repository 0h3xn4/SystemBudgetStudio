"""Stacked time plots with eclipse and pass shading, zoom, pan and cursors.

Draws a `PlotSpec` (the same description the report renderer uses). The wheel zooms around the
pointer, dragging pans, double-click shows everything, hovering moves a cursor with a readout of
every series, a click pins a second cursor and the readout then shows the differences, and
Escape or a right click unpins.

A click on a legend entry hides that series and a second click shows it again; Shift-click keeps
only that one of its panel (again to bring the others back). Markers (for example the intervals
that break a limit) are drawn as a bar along the top of every panel and can be clicked (D-162).

The plot itself (panels, shading, series) is drawn into a picture that is kept until the data, the
view, the size or the shading change; moving the cursor draws only the cursor lines and the
readout on top of it, so hovering over a plot of 600,000 points per series stays quick (D-147).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QLineF, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QFocusEvent,
    QFontMetrics,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QPolygonF,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from budget_core.plots.envelope import EnvelopeCache
from budget_core.plots.spec import (
    Panel,
    PlotSpec,
    nice_ticks,
    value_at,
    visible_range,
)
from budget_gui import theme
from budget_gui.plot_metrics import PLOT
from budget_gui.time_axis import ElapsedAxis, TimeAxis


def _hms_full(seconds: float) -> str:
    total = int(round(abs(seconds)))
    days, rest = divmod(total, 86400)
    hours, rest = divmod(rest, 3600)
    minutes, secs = divmod(rest, 60)
    prefix = "-" if seconds < 0 else ""
    return prefix + (f"{days}d " if days else "") + f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _number(value: float) -> str:
    if value != 0 and (abs(value) >= 1e6 or abs(value) < 0.01):
        return f"{value:.3g}"
    if abs(value) >= 1000:
        return f"{value:.0f}"
    return f"{value:.3f}".rstrip("0").rstrip(".") or "0"


MARKER_MIN_WIDTH = 3.0


@dataclass(frozen=True)
class PlotMarker:
    """A stretch of time worth looking at, for example an interval that breaks a limit."""

    start_s: float
    end_s: float
    label: str = ""


@dataclass(frozen=True)
class LegendEntry:
    panel: int
    label: str
    colour: str
    hidden: bool
    rect: QRectF


class PlotWidget(QWidget):
    view_changed = Signal()
    cursor_changed = Signal(object)  # seconds, or None when the pointer leaves
    marker_clicked = Signal(int)  # index into markers()

    def __init__(self) -> None:
        super().__init__()
        self._spec: PlotSpec | None = None
        self._view = (0.0, 1.0)
        self._cursor: float | None = None
        self._pinned: float | None = None
        self._drag: tuple[float, float, float] | None = None
        self._moved = False
        self._info: Callable[[float], str] | None = None
        self._shading = True
        self._layer: QPixmap | None = None  # the plot without the cursors, see paintEvent
        self._layer_key: tuple[object, ...] | None = None
        self._ranges: dict[int, tuple[float, float]] = {}  # y range of a panel: data only
        self._envelopes = EnvelopeCache()  # block summaries of the series, made once per plot
        self._hidden: set[tuple[int, str]] = set()  # (panel, legend label) switched off
        self._markers: list[PlotMarker] = []
        self._selected: int | None = None
        self._axis: TimeAxis = ElapsedAxis()
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(theme.px(theme.PLOT_MIN_HEIGHT))
        self.setFont(theme.ui_font(theme.TYPE_SMALL))  # labels and legends: the small type size
        theme.manager().changed.connect(self._theme_changed)

    def _theme_changed(self) -> None:
        self.setFont(theme.ui_font(theme.TYPE_SMALL))
        self._layer = None
        self.update()

    # ---- data --------------------------------------------------------------------------------
    def set_spec(self, spec: PlotSpec | None) -> None:
        self._spec = spec
        self._ranges = {}
        self._envelopes.clear()
        self._layer = None
        self._hidden = set()
        self._markers, self._selected = [], None
        if spec is not None:
            self._view = (spec.x_min_s, spec.x_max_s)
            self.setMinimumHeight(
                PLOT.top + PLOT.bottom + len(spec.panels) * (PLOT.min_panel + PLOT.gap) - PLOT.gap
            )
        self._cursor = self._pinned = None
        self.update()
        self.view_changed.emit()

    def spec(self) -> PlotSpec | None:
        return self._spec

    def set_shading(self, enabled: bool) -> None:
        self._shading = enabled
        self._layer = None
        self.update()

    def set_info_provider(self, provider: Callable[[float], str] | None) -> None:
        """Extra text for the readout at a time (for example the spacecraft mode)."""
        self._info = provider

    def set_time_axis(self, axis: TimeAxis) -> None:
        """Elapsed time, UTC or orbit number; kept when a new plot is set."""
        self._axis = axis
        self._layer = None
        self.update()

    def time_axis(self) -> TimeAxis:
        return self._axis

    def axis_title(self) -> str:
        start, end = self._view
        return self._axis.title(start, end)

    # ---- legend: hide and solo ---------------------------------------------------------------
    def legend_entries(self) -> list[LegendEntry]:
        """The legend of every panel: where each entry is, and whether it is switched off."""
        spec = self._spec
        if spec is None:
            return []
        metrics = QFontMetrics(self.font())
        found: list[LegendEntry] = []
        for index, (panel, rect) in enumerate(zip(spec.panels, self._panel_rects(), strict=True)):
            title_y = rect.top() - 5
            x = rect.left() + metrics.horizontalAdvance(panel.y_label) + 24
            for label, colour in self._panel_entries(panel).items():
                width = 21 + metrics.horizontalAdvance(label)
                found.append(
                    LegendEntry(
                        index,
                        label,
                        colour,
                        (index, label) in self._hidden,
                        QRectF(x - 2, title_y - 13, width + 4, 16),
                    )
                )
                x += width + 18
        return found

    @staticmethod
    def _panel_entries(panel: Panel) -> dict[str, str]:
        """One legend entry per label (a series may be split by pass), in drawing order."""
        entries: dict[str, str] = {}
        for s in panel.series:
            entries.setdefault(s.label, s.color)
        for h in panel.hlines:
            entries.setdefault(h.label, h.color)
        return entries

    def toggle_series(self, panel: int, label: str) -> None:
        self._hidden ^= {(panel, label)}
        self._layer = None
        self.update()

    def solo_series(self, panel: int, label: str) -> None:
        """Keep only this entry of its panel; when it is already the only one, show them all."""
        if self._spec is None or not 0 <= panel < len(self._spec.panels):
            return
        others = {(panel, other) for other in self._panel_entries(self._spec.panels[panel])}
        others.discard((panel, label))
        if others <= self._hidden and (panel, label) not in self._hidden:
            self._hidden -= others
        else:
            self._hidden = (self._hidden - {(panel, label)}) | others
        self._layer = None
        self.update()

    def _is_hidden(self, panel: int, label: str) -> bool:
        return (panel, label) in self._hidden

    # ---- markers -----------------------------------------------------------------------------
    def set_markers(self, markers: list[PlotMarker], selected: int | None = None) -> None:
        self._markers, self._selected = list(markers), selected
        self._layer = None
        self.update()

    def markers(self) -> list[PlotMarker]:
        return list(self._markers)

    def _marker_at(self, x: float) -> int | None:
        """The marker under a horizontal position (the nearest when several are close)."""
        best: tuple[float, int] | None = None
        for index, marker in enumerate(self._markers):
            a, b = self.time_to_x(marker.start_s), self.time_to_x(marker.end_s)
            if b - a < MARKER_MIN_WIDTH:
                a, b = (a + b) / 2 - MARKER_MIN_WIDTH / 2, (a + b) / 2 + MARKER_MIN_WIDTH / 2
            gap = max(a - x, x - b, 0.0)
            if gap <= 2.0 and (best is None or gap < best[0]):
                best = (gap, index)
        return None if best is None else best[1]

    # ---- view --------------------------------------------------------------------------------
    def view(self) -> tuple[float, float]:
        return self._view

    def _limits(self) -> tuple[float, float]:
        return (self._spec.x_min_s, self._spec.x_max_s) if self._spec else (0.0, 1.0)

    def set_view(self, start: float, end: float) -> None:
        lo, hi = self._limits()
        width = min(max(end - start, 1.0), hi - lo)
        start = min(max(start, lo), hi - width)
        self._view = (start, start + width)
        self._layer = None
        self.update()
        self.view_changed.emit()

    def zoom(self, factor: float, center_s: float | None = None) -> None:
        start, end = self._view
        center = (start + end) / 2.0 if center_s is None else center_s
        width = (end - start) / factor
        ratio = (center - start) / (end - start) if end > start else 0.5
        self.set_view(center - ratio * width, center - ratio * width + width)

    def pan(self, delta_s: float) -> None:
        start, end = self._view
        self.set_view(start + delta_s, end + delta_s)

    def reset_view(self) -> None:
        self.set_view(*self._limits())

    def _plot_width(self) -> float:
        return max(self.width() - PLOT.left - PLOT.right, 1)

    def time_to_x(self, t: float) -> float:
        start, end = self._view
        return PLOT.left + (t - start) / max(end - start, 1e-9) * self._plot_width()

    def x_to_time(self, x: float) -> float:
        start, end = self._view
        return start + (x - PLOT.left) / self._plot_width() * (end - start)

    def _panel_rects(self) -> list[QRectF]:
        count = len(self._spec.panels) if self._spec else 0
        if count == 0:
            return []
        height = (self.height() - PLOT.top - PLOT.bottom - (PLOT.gap * (count - 1))) / count
        return [
            QRectF(
                PLOT.left,
                PLOT.top + i * (height + PLOT.gap) + PLOT.title,
                self._plot_width(),
                height - PLOT.title,
            )
            for i in range(count)
        ]

    # ---- cursors -----------------------------------------------------------------------------
    def cursor_s(self) -> float | None:
        return self._cursor

    def pinned_s(self) -> float | None:
        return self._pinned

    def set_cursor(self, t: float | None) -> None:
        self._cursor = t
        self.cursor_changed.emit(t)
        self.update()

    def pin_cursor(self, t: float | None) -> None:
        self._pinned = t
        self.update()

    def readout_lines(self, t: float) -> list[str]:
        """What the readout shows at time `t`: time, the info provider's text, every series. With a
        pinned cursor the values are those at `t` with the change since the pinned time."""
        spec = self._spec
        if spec is None:
            return []
        lines = [f"t = {_hms_full(t)}"]
        if self._pinned is not None:
            lines.append(
                f"pinned {_hms_full(self._pinned)}, difference {_hms_full(t - self._pinned)}"
            )
        if self._info is not None:
            lines.extend(self._info(t).splitlines())
        for panel in spec.panels:
            for series in panel.series:
                value = value_at(series, t, spec.x_max_s)
                if value is None:
                    continue
                text = f"{series.label}: {_number(value * panel.y_scale)}"
                if self._pinned is not None:
                    before = value_at(series, self._pinned, spec.x_max_s)
                    if before is not None:
                        text += f" ({(value - before) * panel.y_scale:+.4g})"
                lines.append(text)
        return lines

    # ---- painting ----------------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        painter = QPainter(self)
        spec = self._spec
        if spec is None:
            t = theme.tokens()
            painter.fillRect(self.rect(), QColor(t.plot_bg))
            painter.setPen(QColor(t.text_muted))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No results to show")
            return
        painter.drawPixmap(0, 0, self._plot_layer(spec))
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_cursors(painter, self._panel_rects())
        self._paint_focus(painter)

    def _paint_focus(self, painter: QPainter) -> None:
        """The focus ring of the window, around a plot that has the keyboard (it is not a
        control of the style sheet, so it paints its own)."""
        if not self.hasFocus():
            return
        ring = theme.px(theme.FOCUS_RING)
        painter.setPen(QPen(QColor(theme.tokens().focus), ring))
        painter.drawRect(self.rect().adjusted(ring // 2, ring // 2, -ring, -ring))

    def focusInEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        super().focusInEvent(event)
        self.update()

    def focusOutEvent(self, event: QFocusEvent) -> None:  # noqa: N802
        super().focusOutEvent(event)
        self.update()

    def _plot_layer(self, spec: PlotSpec) -> QPixmap:
        """The plot without the cursors, drawn again only when something it shows changed."""
        ratio = self.devicePixelRatioF()
        key = (
            self.size().width(),
            self.size().height(),
            ratio,
            self._view,
            self._shading,
            id(spec),
            theme.tokens().name,
            id(self._axis),
            frozenset(self._hidden),
            tuple(self._markers),
            self._selected,
        )
        if self._layer is not None and self._layer_key == key:
            return self._layer
        layer = QPixmap(int(self.width() * ratio), int(self.height() * ratio))
        layer.setDevicePixelRatio(ratio)
        painter = QPainter(layer)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(QRectF(0, 0, self.width(), self.height()), QColor(theme.tokens().plot_bg))
        rects = self._panel_rects()
        ticks = [
            (t, label)
            for t, label in self._axis.ticks(*self._view)
            if self._view[0] - 1e-9 <= t <= self._view[1] + 1e-9
        ]
        for index, rect in enumerate(rects):
            self._paint_panel(painter, spec, index, rect, index == len(rects) - 1, ticks)
        painter.end()
        self._layer, self._layer_key = layer, key
        return layer

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        self._layer = None
        super().resizeEvent(event)

    def _y_range(self, panel: Panel) -> tuple[float, float]:
        """The y range of a panel. It depends on the data only (not on the view), so it is worked
        out once per plot: scaling and scanning 600,000 points per series is the slow part."""
        cached = self._ranges.get(id(panel))
        if cached is None:
            lo, hi = visible_range(
                [s.y * panel.y_scale for s in panel.series]
                + [np.array([h.y * panel.y_scale]) for h in panel.hlines],
                None if panel.y_min is None else panel.y_min * panel.y_scale,
                None if panel.y_max is None else panel.y_max * panel.y_scale,
            )
            if hi - lo <= 0.0:  # equal fixed limits would divide by zero below
                hi = lo + 1.0
            cached = self._ranges[id(panel)] = (lo, hi)
        return cached

    def _paint_panel(
        self,
        painter: QPainter,
        spec: PlotSpec,
        index: int,
        rect: QRectF,
        last: bool,
        ticks: list[tuple[float, str]],
    ) -> None:
        panel = spec.panels[index]
        t = theme.tokens()
        lo, hi = self._y_range(panel)

        def sy(v: float) -> float:
            return rect.bottom() - (v - lo) / (hi - lo) * rect.height()

        painter.save()
        painter.setClipRect(rect)
        if self._shading:
            # whole pixels and no antialiasing: a week has hundreds of bands, and blending the
            # edges of each took 0.1 ms
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
            top, height = int(rect.top()), int(rect.height())
            for band in spec.bands:
                colour = theme.plot_colour(t, band.color)
                colour.setAlpha(t.band_alpha)
                for a, b in band.intervals:
                    x0, x1 = self.time_to_x(a), self.time_to_x(b)
                    if x1 >= rect.left() and x0 <= rect.right():
                        left = int(x0)
                        painter.fillRect(left, top, max(int(x1 + 0.999) - left, 1), height, colour)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(QPen(QColor(t.plot_grid), 1))
        for tick in nice_ticks(lo, hi, 4):
            painter.drawLine(QPointF(rect.left(), sy(tick)), QPointF(rect.right(), sy(tick)))
        start, end = self._view
        for tick, _label in ticks:
            x = self.time_to_x(tick)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
        buckets = max(int(rect.width()), 50)
        for series in panel.series:
            if self._is_hidden(index, series.label):
                continue
            drawn = self._envelopes.points(series, start, end, spec.x_max_s, buckets)
            if len(drawn.x) < 2:
                continue
            sx = PLOT.left + (drawn.x - start) / max(end - start, 1e-9) * self._plot_width()
            sy_ = rect.bottom() - (drawn.y * panel.y_scale - lo) / (hi - lo) * rect.height()
            painter.setPen(QPen(theme.plot_colour(t, series.color), 1.6))
            if drawn.pairs:
                # a reduced series: one short line per bucket (a thick pen along a zigzag as tall
                # as the panel took 0.4 s per series to stroke)
                painter.drawLines(
                    list(
                        map(
                            QLineF,
                            sx[0::2].tolist(),
                            sy_[0::2].tolist(),
                            sx[1::2].tolist(),
                            sy_[1::2].tolist(),
                        )
                    )
                )
            else:
                painter.drawPolyline(
                    QPolygonF([QPointF(float(a), float(b)) for a, b in zip(sx, sy_, strict=True)])
                )
        for hline in panel.hlines:
            if self._is_hidden(index, hline.label):
                continue
            pen = QPen(theme.plot_colour(t, hline.color), 1.2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            y = sy(hline.y * panel.y_scale)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
        self._paint_markers(painter, rect)
        painter.restore()

        painter.setPen(QPen(QColor(t.plot_ink), 1))
        painter.drawRect(rect)
        text_font = painter.font()
        painter.setFont(theme.mono_font(theme.TYPE_SMALL))  # numbers have equal digits (D-178)
        for tick in nice_ticks(lo, hi, 4):
            painter.drawText(
                QRectF(0, sy(tick) - 9, PLOT.left - 6, 18),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                _number(tick),
            )
        painter.setFont(text_font)
        painter.setPen(QColor(t.plot_ink))
        title_y = rect.top() - 5
        painter.drawText(QPointF(rect.left(), title_y), panel.y_label)
        for entry in (e for e in self.legend_entries() if e.panel == index):
            x, line_y = entry.rect.left() + 2, entry.rect.center().y()
            faded = QColor(t.plot_muted)
            colour = theme.plot_colour(t, entry.colour)
            if entry.hidden:
                colour = QColor(t.plot_grid)
                faded = QColor(t.text_muted)
            painter.setPen(QPen(colour, 3))
            painter.drawLine(QPointF(x, line_y), QPointF(x + 16, line_y))
            font = painter.font()
            font.setStrikeOut(entry.hidden)
            painter.setFont(font)
            painter.setPen(faded)
            painter.drawText(QPointF(x + 21, title_y), entry.label)
            font.setStrikeOut(False)
            painter.setFont(font)
        if last:
            painter.setPen(QColor(t.plot_ink))
            for tick, label in ticks:
                x_tick = self.time_to_x(tick)
                if rect.left() - 1 <= x_tick <= rect.right() + 1 and x_tick + 30 <= self.width():
                    painter.drawText(
                        QRectF(x_tick - 30, rect.bottom() + 4, 60, 16),
                        Qt.AlignmentFlag.AlignHCenter,
                        label,
                    )
            painter.drawText(
                QRectF(rect.left(), rect.bottom() + 18, rect.width(), 16),
                Qt.AlignmentFlag.AlignHCenter,
                self._axis.title(start, end),
            )

    def _paint_markers(self, painter: QPainter, rect: QRectF) -> None:
        """A bar along the top edge for each marker, and the selected one shaded down the panel.
        Whole pixels and no antialiasing, like the bands."""
        if not self._markers:
            return
        fail = QColor(theme.tokens().status(theme.Status.FAIL).fg)
        shade = QColor(fail)
        shade.setAlpha(46)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        top, height = int(rect.top()), int(rect.height())
        for index, marker in enumerate(self._markers):
            x0, x1 = self.time_to_x(marker.start_s), self.time_to_x(marker.end_s)
            if x1 < rect.left() or x0 > rect.right():
                continue
            left = int(x0)
            width = max(int(x1 + 0.999) - left, int(MARKER_MIN_WIDTH))
            if index == self._selected:
                painter.fillRect(left, top, width, height, shade)
            painter.fillRect(left, top, width, PLOT.marker_bar, fail)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    def _paint_cursors(self, painter: QPainter, rects: list[QRectF]) -> None:
        tk = theme.tokens()
        if not rects:
            return
        top, bottom = rects[0].top(), rects[-1].bottom()
        for t, dash in (
            (self._pinned, Qt.PenStyle.SolidLine),
            (self._cursor, Qt.PenStyle.DashLine),
        ):
            if t is None:
                continue
            x = self.time_to_x(t)
            if rects[0].left() <= x <= rects[0].right():
                painter.setPen(QPen(QColor(tk.plot_ink), 1, dash))
                painter.drawLine(QPointF(x, top), QPointF(x, bottom))
        if self._cursor is None:
            return
        lines = self.readout_lines(self._cursor)
        painter.setFont(theme.mono_font(theme.TYPE_SMALL))
        metrics = QFontMetrics(painter.font())
        width = max(metrics.horizontalAdvance(t) for t in lines) + 16
        height = len(lines) * metrics.height() + 10
        x = self.time_to_x(self._cursor) + 12
        if x + width > self.width() - PLOT.right:
            x = self.time_to_x(self._cursor) - width - 12
        box = QRectF(max(x, PLOT.left + 2), top + 4, width, height)
        painter.fillRect(box, QColor(tk.plot_readout_bg))
        painter.setPen(QPen(QColor(tk.border_strong), 1))
        painter.drawRect(box)
        painter.setPen(QColor(tk.plot_ink))
        for i, text in enumerate(lines):
            painter.drawText(
                QPointF(box.left() + 8, box.top() + 5 + (i + 1) * metrics.height() - 4), text
            )

    # ---- mouse -------------------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        self.zoom(1.25 ** (event.angleDelta().y() / 120.0), self.x_to_time(event.position().x()))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.pin_cursor(None)
        elif event.button() == Qt.MouseButton.LeftButton:
            position = event.position()
            for entry in self.legend_entries():
                if entry.rect.contains(position):
                    if event.modifiers() & (
                        Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.AltModifier
                    ):
                        self.solo_series(entry.panel, entry.label)
                    else:
                        self.toggle_series(entry.panel, entry.label)
                    return
            if self._markers and any(
                r.top() - 1 <= position.y() <= r.top() + PLOT.marker_hit
                for r in self._panel_rects()
            ):
                hit = self._marker_at(position.x())
                if hit is not None:
                    self.marker_clicked.emit(hit)
                    return
            self._drag = (event.position().x(), *self._view)
            self._moved = False

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._spec is None:
            return
        x = event.position().x()
        if self._drag is not None:
            x0, start, end = self._drag
            if abs(x - x0) > 3:
                self._moved = True
            if self._moved:
                shift = -(x - x0) / self._plot_width() * (end - start)
                self.set_view(start + shift, end + shift)
            return
        inside = PLOT.left <= x <= self.width() - PLOT.right
        self.set_cursor(self.x_to_time(x) if inside else None)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._drag is not None and not self._moved and self._spec is not None:
            x = event.position().x()
            if PLOT.left <= x <= self.width() - PLOT.right:
                self.pin_cursor(self.x_to_time(x))
        self._drag = None

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self.reset_view()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802
        if event.key() == Qt.Key.Key_Escape:
            self.pin_cursor(None)
        else:
            super().keyPressEvent(event)

    def leaveEvent(self, event: object) -> None:  # noqa: N802
        self.set_cursor(None)
