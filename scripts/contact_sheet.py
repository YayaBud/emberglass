"""
Quick contact sheet of rendered sprites, for reviewing a batch in one look.

    python scripts/contact_sheet.py <dir> <out.png> [cols] [cell]
"""

import os
import sys
from PIL import Image, ImageDraw, ImageFont

src = sys.argv[1] if len(sys.argv) > 1 else "d:/assests/renders/sheet_sprites_detailed"
out = sys.argv[2] if len(sys.argv) > 2 else "d:/assests/renders/contact.png"
cols = int(sys.argv[3]) if len(sys.argv) > 3 else 5
cell = int(sys.argv[4]) if len(sys.argv) > 4 else 340

files = sorted(f for f in os.listdir(src) if f.lower().endswith(".png"))
rows = (len(files) + cols - 1) // cols
pad, label_h = 10, 22
W = cols * (cell + pad) + pad
H = rows * (cell + pad + label_h) + pad

sheet = Image.new("RGB", (W, H), (21, 28, 36))
draw = ImageDraw.Draw(sheet)
try:
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 15)
except Exception:
    font = ImageFont.load_default()

for i, fn in enumerate(files):
    cx, cy = i % cols, i // cols
    x = pad + cx * (cell + pad)
    y = pad + cy * (cell + pad + label_h)
    try:
        im = Image.open(os.path.join(src, fn)).convert("RGBA")
        bb = im.getbbox()
        if bb:
            im = im.crop(bb)
        r = min(cell / im.width, cell / im.height)
        im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))),
                       Image.Resampling.LANCZOS)
        sheet.paste(im, (x + (cell - im.width) // 2,
                         y + (cell - im.height) // 2), im)
    except Exception as e:
        draw.text((x + 8, y + 8), "ERR " + str(e)[:30], font=font, fill=(220, 90, 90))
    draw.text((x + cell // 2, y + cell + 4), fn[:-4], font=font,
              fill=(150, 170, 190), anchor="mt")

sheet.save(out)
print(f"{len(files)} sprites -> {out}  ({W}x{H})")
