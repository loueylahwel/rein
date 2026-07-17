"""Generate the Rein launcher icon (1024x1024) + adaptive foreground.

Run with the agent venv python (has Pillow):
    agent/.venv/Scripts/python scripts/make_icon.py
Outputs to app/assets/icon/ and agent/rein.ico.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "app" / "assets" / "icon"
OUT.mkdir(parents=True, exist_ok=True)

S = 1024
TEAL = (13, 148, 136)    # deep teal
GREEN = (34, 197, 94)    # emerald
WHITE = (255, 255, 255, 255)
FONT_PATH = "C:/Windows/Fonts/segoeuib.ttf"  # Segoe UI Bold


def lerp(a, b, t):
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def gradient():
    g = Image.new("RGB", (256, 256))
    px = g.load()
    for yy in range(256):
        for xx in range(256):
            px[xx, yy] = lerp(TEAL, GREEN, (xx + yy) / 510)
    return g.resize((S, S), Image.BICUBIC)


def draw_glyph(d, strap_fill):
    font = ImageFont.truetype(FONT_PATH, 640)
    # centered "R"
    bbox = d.textbbox((0, 0), "R", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((S - tw) / 2 - bbox[0], (S - th) / 2 - bbox[1] - 60), "R",
           font=font, fill=WHITE)
    # rein strap: a bold arc sweeping under the R like a rein loop
    d.arc([162, 520, 862, 1020], start=20, end=160, fill=strap_fill, width=54)


# ---- launcher icon: gradient rounded square + white glyph ----
icon = gradient().convert("RGBA")
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, S, S], radius=200, fill=255)
icon.putalpha(mask)
draw_glyph(ImageDraw.Draw(icon), WHITE)
icon.save(OUT / "icon.png")

# ---- adaptive foreground: glyph only on transparent, ~60% safe zone ----
fg = Image.new("RGBA", (S, S), (0, 0, 0, 0))
layer = Image.new("RGBA", (S, S), (0, 0, 0, 0))
draw_glyph(ImageDraw.Draw(layer), WHITE)
layer = layer.resize((614, 614), Image.LANCZOS)
fg.paste(layer, ((S - 614) // 2, (S - 614) // 2), layer)
fg.save(OUT / "icon_foreground.png")

# ---- ico for the Windows exes ----
icon.save(ROOT / "agent" / "rein.ico",
          sizes=[(16, 16), (32, 32), (48, 48), (256, 256)])

print("wrote", OUT / "icon.png", ", icon_foreground.png and agent/rein.ico")
