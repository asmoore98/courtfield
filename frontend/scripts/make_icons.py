"""Draw the app icon: a court seen from above, white lines on court blue.

    python scripts/make_icons.py   # writes PNGs into public/
"""
from pathlib import Path

from PIL import Image, ImageDraw

BLUE = (29, 79, 143)
LINE = (255, 255, 255)
OUT = Path(__file__).resolve().parent.parent / "public"


def court(size: int, inset: float) -> Image.Image:
    """inset: fraction of the canvas kept clear around the court (maskable icons need ~10%+)."""
    s = size * 4  # draw large, scale down for clean edges
    img = Image.new("RGB", (s, s), BLUE)
    d = ImageDraw.Draw(img)
    m = s * inset
    w = max(4, round(s * 0.028))
    # court is taller than wide, like a tennis court seen from above
    cw = (s - 2 * m) * 0.62
    x0, x1 = (s - cw) / 2, (s + cw) / 2
    y0, y1 = m, s - m
    d.rectangle([x0, y0, x1, y1], outline=LINE, width=w)                     # doubles lines
    inner = cw * 0.125
    d.line([x0 + inner, y0, x0 + inner, y1], fill=LINE, width=w)              # singles sidelines
    d.line([x1 - inner, y0, x1 - inner, y1], fill=LINE, width=w)
    cy = (y0 + y1) / 2
    d.line([x0 - w * 1.5, cy, x1 + w * 1.5, cy], fill=LINE, width=round(w * 1.6))  # net
    sv = (y1 - y0) * 0.23
    d.line([x0 + inner, cy - sv, x1 - inner, cy - sv], fill=LINE, width=w)   # service lines
    d.line([x0 + inner, cy + sv, x1 - inner, cy + sv], fill=LINE, width=w)
    d.line([s / 2, cy - sv, s / 2, cy + sv], fill=LINE, width=w)              # center service line
    return img.resize((size, size), Image.LANCZOS)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    court(192, 0.14).save(OUT / "icon-192.png")
    court(512, 0.14).save(OUT / "icon-512.png")
    court(512, 0.22).save(OUT / "icon-maskable-512.png")
    court(180, 0.14).save(OUT / "apple-touch-icon.png")
    court(64, 0.1).save(OUT / "favicon.png")
    print("icons written to", OUT)
