"""Generate PWA icons deterministically with Pillow.

Run: python scripts/make_icons.py
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / "gymlog" / "static" / "icons"
OUT.mkdir(parents=True, exist_ok=True)

BG = (15, 17, 21, 255)
PANEL = (27, 31, 38, 255)
RED = (180, 35, 52, 255)
RED_BRIGHT = (213, 50, 70, 255)
LIGHT = (238, 241, 245, 255)
GREY = (154, 164, 178, 255)


def draw_icon(size: int, maskable: bool = False) -> Image.Image:
    scale = 4
    s = size * scale
    img = Image.new("RGBA", (s, s), BG)
    d = ImageDraw.Draw(img)

    cx, cy = s / 2, s / 2
    factor = 0.78 if maskable else 1.0

    def box(x0, y0, x1, y1):
        return (
            cx + (x0 - 0.5) * s * factor,
            cy + (y0 - 0.5) * s * factor,
            cx + (x1 - 0.5) * s * factor,
            cy + (y1 - 0.5) * s * factor,
        )

    # Flat panel gives the icon depth without any decorative theme.
    d.rounded_rectangle(box(0.08, 0.08, 0.92, 0.92), radius=int(s * 0.10), fill=PANEL)

    # Bar.
    d.rounded_rectangle(box(0.24, 0.465, 0.76, 0.535), radius=int(s * 0.018), fill=LIGHT)
    d.rounded_rectangle(box(0.43, 0.455, 0.57, 0.545), radius=int(s * 0.014), fill=GREY)

    # Plates.
    plate_specs = [
        (0.13, 0.19, 0.32, 0.68, RED),
        (0.19, 0.25, 0.42, 0.58, LIGHT),
        (0.81, 0.87, 0.32, 0.68, RED),
        (0.75, 0.81, 0.42, 0.58, LIGHT),
    ]
    for x0, x1, y0, y1, color in plate_specs:
        d.rounded_rectangle(box(x0, y0, x1, y1), radius=int(s * 0.022), fill=color)

    # Small centre marker.
    d.rounded_rectangle(box(0.47, 0.47, 0.53, 0.53), radius=int(s * 0.012), fill=RED_BRIGHT)

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
