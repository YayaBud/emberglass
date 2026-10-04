"""One labelled sheet of every city-kit render (renders/citykit/meta.json).

    python D:/assests/scripts/forge/citykit/sheet.py

Writes renders/citykit/emberglass_city_kit.png (and a .jpg).
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
REN = os.path.join(ROOT, "renders", "citykit")
W = 3200
SECTIONS = [("building", "BUILDINGS", 380), ("variant", "VARIANTS", 300), ("structure", "WALLS  ·  GROUND  ·  WATER", 300),
            ("prop", "PROPS", 215), ("ship", "SHIPS", 380), ("reused", "REUSED FROM THE SNOW / DESERT KITS (snow off, retextured)", 180)]
BG, CARD, INK, DIM, GOLD = (20, 24, 30), (30, 36, 44), (226, 220, 204), (140, 150, 160), (214, 170, 96)


def font(size, bold=False):
    for f in (("georgiab.ttf" if bold else "georgia.ttf"), "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(os.path.join("C:/Windows/Fonts", f), size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    meta = json.load(open(os.path.join(REN, "meta.json")))
    pad, lab = 14, 44
    layout, y = [], 170
    for cat, title, cell in SECTIONS:
        items = [m for m in meta if m["cat"] == cat]
        if not items:
            continue
        cols = (W - pad) // (cell + pad)
        rows = (len(items) + cols - 1) // cols
        layout.append((title, cell, cols, items, y))
        y += 64 + rows * (cell + lab + pad) + 20
    H = y + 40
    sheet = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(sheet)
    d.text((pad * 3, 40), "EMBERGLASS  —  CITY ASSET KIT", font=font(64, True), fill=GOLD)
    total = sum(1 for m in meta if m["cat"] != "reused")
    d.text((pad * 3, 118), f"{total} new assets  ·  8 new surfaces (clay tile, ashlar, flagstone, cloth x3, stained "
                           f"glass, crops)  ·  textured at 52 texels/m  ·  tris per asset shown", font=font(26), fill=DIM)
    f_name, f_tri = font(20, True), font(16)
    for title, cell, cols, items, y0 in layout:
        d.text((pad * 3, y0), f"{title}  ({len(items)})", font=font(34, True), fill=GOLD)
        d.line((pad * 3, y0 + 48, W - pad * 3, y0 + 48), fill=(70, 64, 52), width=2)
        x_off = (W - cols * (cell + pad) + pad) // 2
        for i, m in enumerate(items):
            cx = x_off + (i % cols) * (cell + pad)
            cy = y0 + 64 + (i // cols) * (cell + lab + pad)
            d.rounded_rectangle((cx, cy, cx + cell, cy + cell + lab), 10, fill=CARD)
            try:
                im = Image.open(m["file"]).convert("RGBA")
                bb = im.getbbox()
                if bb:
                    im = im.crop(bb)
                r = min((cell - 16) / im.width, (cell - 16) / im.height)
                im = im.resize((max(1, int(im.width * r)), max(1, int(im.height * r))), Image.LANCZOS)
                sheet.paste(im, (cx + (cell - im.width) // 2, cy + (cell - im.height) // 2), im)
            except OSError:
                d.text((cx + 10, cy + 10), "missing", font=f_tri, fill=(220, 90, 90))
            d.text((cx + cell // 2, cy + cell + 4), m["name"].replace("_", " "), font=f_name, fill=INK, anchor="mt")
            sz = m["size"]
            d.text((cx + cell // 2, cy + cell + 26), f"{m['tris']:,} tris  ·  {sz[0]:.0f}x{sz[1]:.0f}x{sz[2]:.0f} m",
                   font=f_tri, fill=DIM, anchor="mt")
    png = os.path.join(REN, "emberglass_city_kit.png")
    sheet.save(png)
    sheet.convert("RGB").save(png[:-4] + ".jpg", quality=90)
    print(f"sheet: {len(meta)} assets -> {png} ({W}x{H})")


if __name__ == "__main__":
    main()
