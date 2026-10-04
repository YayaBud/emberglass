"""The four target scenes side by side: the concept sheet, a previous state, and a tour.

    python D:/assests/scripts/forge/vs_target.py <tour_dir> <out.jpg> [label]

The target and the 30 Sep (night) columns are cut from `scratch/tour_2026-09-30/CITY_vs_TARGET.jpg`
(its left and right columns), so every sheet compares against the same two references.
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "scratch", "tour_2026-09-30", "CITY_vs_TARGET.jpg")
# (row name, tour frame suffix, row y0..y1 in REF); REF's columns are x 12-606 / 1232-1828
ROWS = [("MARKET SQUARE", "market_square", 95, 425), ("OLD CITY", "old_city", 470, 803),
        ("HARBOUR", "harbour_docks", 850, 1181), ("AGRICULTURAL EDGE", "agricultural_edge", 1238, 1559)]
COLS = [("TARGET", 12, 606), ("30 SEP NIGHT", 1232, 1828)]
W, H = 600, 338


def main(tour, out, label="NOW"):
    ref = Image.open(REF).convert("RGB")
    sheet = Image.new("RGB", (W * 3 + 40, (H + 30) * len(ROWS) + 50), (16, 20, 26))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("georgiab.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    d.text((12, 12), f"CITY vs TARGET  -  target sheet  /  30 Sep night  /  {label}", fill=(222, 190, 120), font=font)
    for r, (name, suffix, y0, y1) in enumerate(ROWS):
        y = 50 + r * (H + 30)
        for c, (col, x0, x1) in enumerate(COLS):
            sheet.paste(ref.crop((x0, y0, x1, y1)).resize((W, H)), (10 + c * (W + 10), y + 24))
            d.text((10 + c * (W + 10), y), f"{name}  -  {col}", fill=(235, 235, 235), font=font)
        frame = next((f for f in sorted(os.listdir(tour)) if f.endswith(suffix + ".png")), None)
        if frame:
            sheet.paste(Image.open(os.path.join(tour, frame)).convert("RGB").resize((W, H)), (10 + 2 * (W + 10), y + 24))
        d.text((10 + 2 * (W + 10), y), f"{name}  -  {label}", fill=(235, 235, 235), font=font)
    sheet.save(out, quality=88)
    print("vs_target ->", out)


if __name__ == "__main__":
    main(*sys.argv[1:])
