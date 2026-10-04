"""Contact sheets of the city walk's captures (renders/citywalk/).

    python D:/assests/scripts/forge/walk_sheet.py [prefix ...]

Four captures per sheet (2 x 2, each at half size), labelled with the file
name, into renders/citywalk/sheets/. With prefixes, only files starting with
one of them (e.g. r04_ r12_).
"""
import os
import sys

from PIL import Image, ImageDraw

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "renders", "citywalk")
OUT = os.path.join(DIR, "sheets")


def main():
    pre = sys.argv[1:]
    files = sorted(f for f in os.listdir(DIR) if f.endswith(".png") and (not pre or any(f.startswith(p) for p in pre)))
    os.makedirs(OUT, exist_ok=True)
    for k in range(0, len(files), 4):
        sheet = Image.new("RGB", (1280, 720), (20, 20, 20))
        d = ImageDraw.Draw(sheet)
        for j, f in enumerate(files[k:k + 4]):
            im = Image.open(os.path.join(DIR, f)).convert("RGB").resize((640, 360), Image.BILINEAR)
            x, y = (j % 2) * 640, (j // 2) * 360
            sheet.paste(im, (x, y))
            d.rectangle((x, y, x + 150, y + 16), fill=(0, 0, 0))
            d.text((x + 4, y + 2), f, fill=(255, 255, 0))
        name = f"sheet_{k // 4:03d}.png" if not pre else f"sheet_{'_'.join(pre)}_{k // 4:02d}.png"
        sheet.save(os.path.join(OUT, name))
    print(f"walk_sheet: {len(files)} captures -> {(len(files) + 3) // 4} sheets in {OUT}")


if __name__ == "__main__":
    main()
