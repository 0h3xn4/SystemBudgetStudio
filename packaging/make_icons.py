"""Draw the application icon (four budget bars under a dashed limit line) as PNG files.

The drawing is the same as docs/images/logo.svg (256 x 256 units); keep the two in step. It is
drawn at eight times the size and reduced, so the edges are smooth and the corners transparent.
The files are committed (assets/icons/); run this only when the drawing changes:

    python packaging/make_icons.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZES = (16, 24, 32, 48, 64, 128, 256)
SCALE = 8
UNITS = 256
BACKGROUND = "#161616"
BARS = (  # x, y, width, height inside the group that is moved by (46, 44)
    (0, 86, 30, 86, "#78a9ff"),
    (40, 58, 30, 114, "#4589ff"),
    (80, 34, 30, 138, "#0f62fe"),
    (120, 14, 30, 158, "#f4f4f4"),
)
ORIGIN = (46, 44)
LIMIT_Y, BASE_Y = 14, 172
DASH, GAP = 8, 7


def draw(size: int) -> Image.Image:
    big = UNITS * SCALE
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    painter = ImageDraw.Draw(image)

    def box(x: float, y: float, w: float, h: float) -> tuple[float, float, float, float]:
        left, top = (x + ORIGIN[0]) * SCALE, (y + ORIGIN[1]) * SCALE
        return left, top, left + w * SCALE - 1, top + h * SCALE - 1

    painter.rounded_rectangle((0, 0, big - 1, big - 1), radius=40 * SCALE, fill=BACKGROUND)
    for x, y, w, h, colour in BARS:
        painter.rectangle(box(x, y, w, h), fill=colour)
    x = -10.0
    while x < 160.0:  # the dashed limit line, 3 units thick
        painter.rectangle(box(x, LIMIT_Y - 1.5, min(DASH, 160.0 - x), 3), fill="#f4f4f4")
        x += DASH + GAP
    painter.rectangle(box(-10, BASE_Y - 1.5, 170, 3), fill="#c6c6c6")  # the base line
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    out = Path(__file__).resolve().parent.parent / "assets" / "icons"
    out.mkdir(parents=True, exist_ok=True)
    for size in SIZES:
        draw(size).save(out / f"logo-{size}.png", optimize=True)
        print(f"logo-{size}.png")


if __name__ == "__main__":
    main()
