"""Make a boot logo for the PF1506: 1920x1080, 24-bit uncompressed BMP, the same
format as the stock bootlogo.bmp. Write it into a copy of bootloader.img with
patch_logo.py.

usage: make_logo.py <font.ttf> <out.bmp> "<title>" ["<subtitle>"]
"""
import sys
from PIL import Image, ImageDraw, ImageFont

font_path, out, title = sys.argv[1:4]
subtitle = sys.argv[4] if len(sys.argv) > 4 else ""
W, H = 1920, 1080
BG, TEXT, MUTED = (233, 237, 243), (27, 31, 39), (95, 104, 120)

img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)


def centered(y, text, size, fill):
    font = ImageFont.truetype(font_path, size)
    w = d.textlength(text, font=font)
    d.text(((W - w) / 2, y), text, font=font, fill=fill)


centered(400 if subtitle else 470, title, 132, TEXT)
if subtitle:
    centered(590, subtitle, 64, MUTED)
img.save(out)  # Pillow writes 24-bit BI_RGB, bottom-up, 54-byte header
print(f"saved {out}")
