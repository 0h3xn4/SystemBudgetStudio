"""The ground track on a latitude-longitude map (2.2.0, D-232).

The sub-satellite point over the scenario, drawn on an equirectangular grid with the stations and
targets of the scenario marked. The tool carries no coastline data (it ships no data it cannot
state the source of), so the map is a graticule; the track, the markers and the labels are what
it shows. Colours come from the theme tokens, sizes from the scale.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPaintEvent, QPen
from PySide6.QtWidgets import QWidget

from budget_core.environment.ground_track import GroundTrack
from budget_gui import theme

MAX_POINTS = 20_000  # the line drawn: more than a screen can show only slows the paint


@dataclass(frozen=True)
class MapSite:
    site_id: str
    kind: str  # ground_station or target
    latitude_deg: float
    longitude_deg: float


class GroundTrackWidget(QWidget):
    """A map of one ground track; `set_track(None)` clears it."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._lines: list[list[tuple[float, float]]] = []
        self._start: tuple[float, float] | None = None
        self._end: tuple[float, float] | None = None
        self._sites: tuple[MapSite, ...] = ()
        self.setMinimumHeight(theme.px(theme.MAP_MIN_HEIGHT))
        self.setFont(theme.ui_font(theme.TYPE_SMALL))
        theme.manager().changed.connect(self.update)

    # ---- data ---------------------------------------------------------------------------------

    def set_track(self, track: GroundTrack | None, sites: Sequence[MapSite] = ()) -> None:
        self._sites = tuple(sites)
        self._lines = []
        self._start = self._end = None
        if track is not None and len(track.latitude_deg):
            lat, lon = track.latitude_deg, track.longitude_deg
            self._start = (float(lon[0]), float(lat[0]))
            self._end = (float(lon[-1]), float(lat[-1]))
            stride = max(1, math.ceil(len(lat) / MAX_POINTS))
            picks = np.unique(np.append(np.arange(0, len(lat), stride), len(lat) - 1))
            x, y = lon[picks], lat[picks]
            # a line is cut where the track crosses the date line, not drawn across the map
            cuts = np.flatnonzero(np.abs(np.diff(x)) > 180.0) + 1
            for part_x, part_y in zip(np.split(x, cuts), np.split(y, cuts), strict=True):
                self._lines.append(
                    [(float(a), float(b)) for a, b in zip(part_x, part_y, strict=True)]
                )
        self.update()

    @property
    def has_track(self) -> bool:
        return bool(self._lines)

    @property
    def line_count(self) -> int:
        """The number of separate stretches of the line (the date line cuts it)."""
        return len(self._lines)

    # ---- painting -----------------------------------------------------------------------------

    def _map_rect(self) -> QRectF:
        left, right, top, bottom = (theme.px(v) for v in theme.MAP_MARGINS)
        area = QRectF(left, top, self.width() - left - right, self.height() - top - bottom)
        width = min(area.width(), area.height() * 2.0)  # 360 by 180 degrees: two to one
        height = width / 2.0
        return QRectF(
            area.left() + (area.width() - width) / 2.0,
            area.top() + (area.height() - height) / 2.0,
            width,
            height,
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        t = theme.tokens()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor(t.plot_bg))
        rect = self._map_rect()
        if rect.width() < 8:
            painter.end()
            return

        def px_of(lon: float, lat: float) -> QPointF:
            return QPointF(
                rect.left() + (lon + 180.0) / 360.0 * rect.width(),
                rect.bottom() - (lat + 90.0) / 180.0 * rect.height(),
            )

        painter.fillRect(rect, QColor(t.surface))
        grid = QPen(QColor(t.plot_grid), 1)
        strong = QPen(QColor(t.border_strong), 1)
        painter.setFont(theme.mono_font(theme.TYPE_SMALL))
        painter.setPen(QColor(t.plot_muted))
        for degrees in range(-90, 91, 30):
            y = px_of(0.0, degrees).y()
            painter.setPen(strong if degrees == 0 else grid)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            painter.setPen(QColor(t.plot_muted))
            painter.drawText(
                QRectF(0, y - theme.px(9), rect.left() - theme.px(6), theme.px(18)),
                int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter),
                f"{degrees}",
            )
        for degrees in range(-180, 181, 30):
            x = px_of(degrees, 0.0).x()
            painter.setPen(strong if degrees == 0 else grid)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            painter.setPen(QColor(t.plot_muted))
            painter.drawText(
                QRectF(x - theme.px(20), rect.bottom() + theme.px(3), theme.px(40), theme.px(16)),
                int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
                f"{degrees}",
            )
        painter.setPen(QPen(QColor(t.border_strong), 1))
        painter.drawRect(rect)

        painter.save()
        painter.setClipRect(rect)
        painter.setPen(QPen(QColor(t.series[0]), 1.4))
        for line in self._lines:
            if len(line) < 2:
                continue
            path = QPainterPath(px_of(*line[0]))
            for lon, lat in line[1:]:
                path.lineTo(px_of(lon, lat))
            painter.drawPath(path)
        painter.restore()

        marker = theme.px(theme.MAP_MARKER)
        painter.setFont(theme.ui_font(theme.TYPE_SMALL))
        for site in self._sites:
            colour = QColor(t.series[1] if site.kind == "ground_station" else t.series[2])
            centre = px_of(site.longitude_deg, site.latitude_deg)
            painter.setPen(QPen(colour, 1.5))
            painter.setBrush(colour)
            if site.kind == "ground_station":
                painter.drawPolygon(
                    [
                        QPointF(centre.x(), centre.y() - marker),
                        QPointF(centre.x() + marker, centre.y()),
                        QPointF(centre.x(), centre.y() + marker),
                        QPointF(centre.x() - marker, centre.y()),
                    ]
                )
            else:
                painter.drawRect(
                    QRectF(centre.x() - marker / 2, centre.y() - marker / 2, marker, marker)
                )
            painter.setPen(QColor(t.text))
            painter.drawText(
                QPointF(centre.x() + marker + theme.px(3), centre.y() + theme.px(4)), site.site_id
            )
        if self._start is not None and self._end is not None:
            start, end = px_of(*self._start), px_of(*self._end)
            colour = QColor(t.series[0])
            painter.setBrush(colour)
            painter.setPen(QPen(colour, 1.5))
            painter.drawEllipse(start, marker, marker)
            painter.setBrush(QColor(t.surface))
            painter.drawEllipse(end, marker, marker)
        if self.hasFocus():
            painter.setPen(QPen(QColor(t.focus), theme.px(theme.FOCUS_RING)))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
        painter.end()
