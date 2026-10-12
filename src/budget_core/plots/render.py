"""PNG rendering of a PlotSpec with Pillow and the bundled IBM Plex fonts.

Drawn at twice the size and scaled down for smooth lines. The same spec and Pillow version give
the same bytes. No files are read except the bundled fonts.
"""

from __future__ import annotations

import io
from dataclasses import replace
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from budget_core.assets import font_path
from budget_core.plots.spec import (
    GREY,
    INK,
    Band,
    HLine,
    Panel,
    PlotSpec,
    finite_runs,
    nice_ticks,
    plot_points,
    tick_labels,
    time_axis,
    visible_range,
)

SCALE = 2
WIDTH_PX = 1400
PANEL_HEIGHT_PX = 260
LEFT, RIGHT, TOP, BOTTOM, GAP = 96, 24, 56, 64, 36
GRID = "#e0e0e0"

Draw = Any


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(font_path(name)), size * SCALE)


def _mix(color: str, weight: float) -> str:
    """The colour blended with white (bands are light, drawn under the lines)."""
    r, g, b = (int(color[i : i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(int(255 - (255 - c) * weight) for c in (r, g, b)))


def _printable(spec: PlotSpec, font: ImageFont.FreeTypeFont) -> PlotSpec:
    """The spec with every character the bundled font lacks (CJK, emoji) replaced by '?', so a
    label shows that something is there instead of an empty box or nothing."""
    missing = font.getmask("\ue000")  # what the font draws for a character it does not have
    blank = (missing.size, bytes(missing))
    known: dict[str, str] = {}

    def fix(text: str) -> str:
        out = []
        for ch in text:
            if ch not in known:
                mask = font.getmask(ch)
                lacking = not ch.isspace() and (mask.size, bytes(mask)) == blank
                known[ch] = "?" if lacking else ch
            out.append(known[ch])
        return "".join(out)

    panels = tuple(
        replace(
            p,
            title=fix(p.title),
            y_label=fix(p.y_label),
            series=tuple(replace(s, label=fix(s.label)) for s in p.series),
            hlines=tuple(replace(h, label=fix(h.label)) for h in p.hlines),
        )
        for p in spec.panels
    )
    bands = tuple(replace(b, label=fix(b.label)) for b in spec.bands)
    return replace(spec, title=fix(spec.title), panels=panels, bands=bands)


def render_png(spec: PlotSpec, width_px: int = WIDTH_PX) -> bytes:
    spec = _printable(spec, _font("IBMPlexSans-Regular.ttf", 13))
    panels = max(len(spec.panels), 1)
    height = TOP + panels * PANEL_HEIGHT_PX + (panels - 1) * GAP + BOTTOM
    image = Image.new("RGB", (width_px * SCALE, height * SCALE), "white")
    draw = ImageDraw.Draw(image)
    regular, bold = _font("IBMPlexSans-Regular.ttf", 13), _font("IBMPlexSans-SemiBold.ttf", 15)
    divisor, unit = time_axis(spec.x_max_s - spec.x_min_s)
    plot_w = width_px - LEFT - RIGHT

    def sx(t: float) -> float:
        span = max(spec.x_max_s - spec.x_min_s, 1e-9)
        return (LEFT + (t - spec.x_min_s) / span * plot_w) * SCALE

    draw.text((LEFT * SCALE, 14 * SCALE), spec.title, fill=INK, font=bold)
    _legend_bands(draw, spec.bands, regular, width_px)
    for index, panel in enumerate(spec.panels):
        top = TOP + index * (PANEL_HEIGHT_PX + GAP)
        last = index == len(spec.panels) - 1
        _panel(draw, panel, spec, sx, top, regular, bold, divisor, unit, last, width_px)
    out = image.resize((width_px, height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    out.save(buffer, format="PNG", optimize=False, compress_level=6)
    return buffer.getvalue()


def _legend_bands(
    draw: Draw, bands: tuple[Band, ...], font: ImageFont.FreeTypeFont, w: int
) -> None:
    x = (w - RIGHT) * SCALE
    for band in reversed(bands):
        label = band.label
        width = draw.textlength(label, font=font)
        x -= width
        draw.text((x, 18 * SCALE), label, fill=INK, font=font)
        x -= 18 * SCALE
        draw.rectangle(
            (x, 18 * SCALE, x + 12 * SCALE, 31 * SCALE),
            fill=_mix(band.color, 1.0),
            outline=GREY,
        )
        x -= 20 * SCALE


def _panel(
    draw: Draw,
    panel: Panel,
    spec: PlotSpec,
    sx: Any,
    top: int,
    regular: ImageFont.FreeTypeFont,
    bold: ImageFont.FreeTypeFont,
    divisor: float,
    unit: str,
    last: bool,
    width_px: int,
) -> None:
    bottom = top + PANEL_HEIGHT_PX
    left_px, right_px = LEFT * SCALE, (width_px - RIGHT) * SCALE
    top_px, bottom_px = top * SCALE, bottom * SCALE
    values = [s.y * panel.y_scale for s in panel.series]
    values += [np.array([h.y * panel.y_scale]) for h in panel.hlines]
    low, high = visible_range(
        values,
        None if panel.y_min is None else panel.y_min * panel.y_scale,
        None if panel.y_max is None else panel.y_max * panel.y_scale,
    )

    def sy(v: float) -> float:
        return bottom_px - (v - low) / (high - low) * (bottom_px - top_px)

    for band in spec.bands:
        for a, b in band.intervals:
            x0, x1 = sx(max(a, spec.x_min_s)), sx(min(b, spec.x_max_s))
            if x1 > x0:
                draw.rectangle(
                    (x0, top_px, max(x1, x0 + 1), bottom_px), fill=_mix(band.color, 0.55)
                )
    y_ticks = nice_ticks(low, high, 5)
    for tick, label in zip(y_ticks, tick_labels(y_ticks), strict=True):
        y = sy(tick)
        draw.line((left_px, y, right_px, y), fill=GRID, width=SCALE)
        draw.text((left_px - 8 * SCALE, y), label, fill=INK, font=regular, anchor="rm")
    x_ticks = nice_ticks(spec.x_min_s / divisor, spec.x_max_s / divisor, 8)
    for tick, label in zip(x_ticks, tick_labels(x_ticks), strict=True):
        t = tick * divisor
        if not spec.x_min_s - 1e-9 <= t <= spec.x_max_s + 1e-9:
            continue
        x = sx(t)
        draw.line((x, top_px, x, bottom_px), fill=GRID, width=SCALE)
        if last:
            draw.text((x, bottom_px + 6 * SCALE), label, fill=INK, font=regular, anchor="ma")
    draw.rectangle((left_px, top_px, right_px, bottom_px), outline=INK, width=SCALE)
    if last:
        label = f"Time since scenario start ({unit})"
        draw.text(
            ((left_px + right_px) / 2, bottom_px + 30 * SCALE),
            label,
            fill=INK,
            font=regular,
            anchor="ma",
        )
    draw.text((left_px, top_px - 11 * SCALE), panel.y_label, fill=INK, font=bold, anchor="lm")

    for hline in panel.hlines:
        _hline(draw, hline, panel, sy, left_px, right_px)
    buckets = max(int(right_px - left_px) // SCALE, 50)
    legend_x = left_px + draw.textlength(panel.y_label, font=bold) + 36 * SCALE
    legend_y = top_px - 11 * SCALE
    shown: set[str] = set()
    entries: list[tuple[str, str]] = []
    for series in panel.series:
        px, py = plot_points(series, spec.x_min_s, spec.x_max_s, spec.x_max_s, buckets)
        for rx, ry in finite_runs(px, py):  # never a line across a missing sample
            points = [
                (sx(float(a)), sy(float(b) * panel.y_scale)) for a, b in zip(rx, ry, strict=True)
            ]
            if len(points) >= 2:
                draw.line(points, fill=series.color, width=int(1.6 * SCALE), joint="curve")
            elif points:  # one sample on its own: a marker, so it is not invisible
                (cx, cy), r = points[0], 2.5 * SCALE
                draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=series.color)
        if series.label not in shown:
            shown.add(series.label)
            entries.append((series.label, series.color))
    for hline in panel.hlines:
        _hline(draw, hline, panel, sy, left_px, right_px)
        entries.append((hline.label, hline.color))
    _legend(draw, entries, legend_x, legend_y, right_px, regular)


def _legend(
    draw: Draw,
    entries: list[tuple[str, str]],
    x: float,
    y: float,
    right: float,
    font: ImageFont.FreeTypeFont,
) -> None:
    """The legend of a panel on one line; entries that do not fit the picture are replaced by
    "+N more" (the line colours and the report tables still name them)."""
    widths = [28 * SCALE + draw.textlength(label, font=font) + 22 * SCALE for label, _ in entries]
    shown = len(entries)
    while shown > 0:
        rest = len(entries) - shown
        more = 0.0 if not rest else draw.textlength(f"+{rest} more", font=font) + 4 * SCALE
        if x + sum(widths[:shown]) + more <= right:
            break
        shown -= 1
    for label, color in entries[:shown]:
        x = _legend_entry(draw, x, y, label, color, font)
    if shown < len(entries):
        draw.text((x, y), f"+{len(entries) - shown} more", fill=INK, font=font, anchor="lm")


def _legend_entry(
    draw: Draw, x: float, y: float, label: str, color: str, font: ImageFont.FreeTypeFont
) -> float:
    draw.line((x, y, x + 22 * SCALE, y), fill=color, width=3 * SCALE)
    draw.text((x + 28 * SCALE, y), label, fill=INK, font=font, anchor="lm")
    return float(x + 28 * SCALE + draw.textlength(label, font=font) + 22 * SCALE)


def _hline(draw: Draw, hline: HLine, panel: Panel, sy: Any, left: float, right: float) -> None:
    y = sy(hline.y * panel.y_scale)
    x = left
    while x < right:  # dashed
        draw.line((x, y, min(x + 10 * SCALE, right), y), fill=hline.color, width=SCALE)
        x += 16 * SCALE


def image_size(png: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(png)) as image:
        return image.size
