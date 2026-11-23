"""Generate PWA icons deterministically with Pillow.

Run: python scripts/make_icons.py
"""

from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "gymlog" / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

CHARCOAL = (17, 16, 15, 255)
IRON = (37, 35, 33, 255)
CRIMSON = (125, 31, 43, 255)
CRIMSON_DARK = (82, 20, 29, 255)
GOLD = (201, 162, 77, 255)
GOLD_LIGHT = (236, 204, 126, 255)
PARCHMENT = (238, 226, 201, 255)


def shield_points(size: int, scale: float = 0.72, y_offset: float = 0.04):
    cx = size / 2
    top = size * y_offset
    width = size * scale
    height = size * scale * 1.12
    left = cx - width / 2
    right = cx + width / 2
    return [
        (left, top + height * 0.12),
        (cx, top),
        (right, top + height * 0.12),
        (right, top + height * 0.58),
        (cx, top + height),
        (left, top + height * 0.58),
    ]


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    s = size * 4
    img = Image.new("RGBA", (s, s), CHARCOAL)
    d = ImageDraw.Draw(img)

    # Subtle stone/iron gradient bands.
    for y in range(0, s, 8):
        shade = int(8 * (y / s))
        d.rectangle([0, y, s, y + 8], fill=(17 + shade, 16 + shade, 15 + shade, 255))

    margin = 0.14 if maskable else 0.06
    pts = shield_points(s, scale=0.72 - (0.14 if maskable else 0), y_offset=margin)
    d.polygon(pts, fill=GOLD)
    inner_pts = shield_points(s, scale=0.66 - (0.14 if maskable else 0), y_offset=margin + 0.012)
    d.polygon(inner_pts, fill=CRIMSON_DARK)
    inner2_pts = shield_points(s, scale=0.61 - (0.14 if maskable else 0), y_offset=margin + 0.022)
    d.polygon(inner2_pts, fill=CRIMSON)

    cx = s / 2
    top = s * margin + s * 0.06
    bottom = s * (0.86 if not maskable else 0.78)

    # Sword blade and guard.
    blade_w = s * (0.075 if not maskable else 0.062)
    d.polygon(
        [
            (cx - blade_w, top + s * 0.34),
            (cx, top),
            (cx + blade_w, top + s * 0.34),
            (cx, top + s * 0.40),
        ],
        fill=PARCHMENT,
    )
    d.line([(cx, top), (cx, top + s * 0.34)], fill=GOLD_LIGHT, width=max(2, int(s * 0.006)))
    guard_y = top + s * 0.36
    d.rounded_rectangle(
        [cx - s * 0.18, guard_y, cx + s * 0.18, guard_y + s * 0.045],
        radius=int(s * 0.02),
        fill=GOLD,
    )
    d.rectangle([cx - s * 0.022, guard_y, cx + s * 0.022, bottom - s * 0.08], fill=GOLD)
    d.ellipse([cx - s * 0.045, bottom - s * 0.11, cx + s * 0.045, bottom - s * 0.02], fill=GOLD_LIGHT)

    # Dumbbell plates crossing behind the sword.
    plate_y = top + s * 0.50
    plate_h = s * 0.10
    d.rounded_rectangle([cx - s * 0.27, plate_y - plate_h * 0.9, cx - s * 0.16, plate_y + plate_h * 0.9], radius=int(s * 0.02), fill=IRON, outline=GOLD, width=max(2, int(s * 0.008)))
    d.rounded_rectangle([cx + s * 0.16, plate_y - plate_h * 0.9, cx + s * 0.27, plate_y + plate_h * 0.9], radius=int(s * 0.02), fill=IRON, outline=GOLD, width=max(2, int(s * 0.008)))
    d.rectangle([cx - s * 0.20, plate_y - s * 0.012, cx + s * 0.20, plate_y + s * 0.012], fill=GOLD_LIGHT)

    return img.resize((size, size), Image.Resampling.LANCZOS)


for name, size, maskable in [
    ("icon-192.png", 192, False),
    ("icon-512.png", 512, False),
    ("icon-maskable-192.png", 192, True),
    ("icon-maskable-512.png", 512, True),
    ("apple-touch-icon.png", 180, False),
    ("favicon-32.png", 32, False),
]:
    draw_icon(size, maskable).save(OUT / name)
    print(f"wrote {OUT / name}")
