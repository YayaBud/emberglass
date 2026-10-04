"""Compose the camera sweep (`-- --camtest --camsweep`) into one labelled sheet.

    python D:/assests/scripts/forge/camera_sweep_sheet.py

Reads renders/camera_sweep/pPP_dDD.png (pitch 5-30 deg by 5, standoff 20-40 m
by 5), writes renders/camera_sweep/camera_sweep_sheet.png and .jpg: rows are
pitch, columns are distance.
"""
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, "renders", "camera_sweep")
PITCH = [5, 10, 15, 20, 25, 30]
DIST = [20, 25, 30, 35, 40]
TW, TH = 480, 270            # thumbnail: 1280x720 / 2.67
LEFT, TOP, PAD = 90, 60, 6


def font(size):
    for name in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def main():
    # a covered or minimised game window stops drawing and every capture is
    # the same stale frame (INVARIANTS; 2026-09-25: all 30 byte-identical) --
    # refuse to compose that as a sweep
    frames = [f for f in (os.path.join(DIR, f"p{p:02d}_d{d}.png") for p in PITCH for d in DIST) if os.path.exists(f)]
    stale = len(frames) - len({open(f, "rb").read() for f in frames})
    if stale:
        raise SystemExit(f"camera sweep: {stale} frame(s) byte-identical to another (stale window); re-run with --always-on-top")
    W = LEFT + len(DIST) * (TW + PAD)
    H = TOP + len(PITCH) * (TH + PAD) + 40
    sheet = Image.new("RGB", (W, H), (18, 18, 20))
    d = ImageDraw.Draw(sheet)
    big, small = font(26), font(18)
    d.text((LEFT, 14), "Emberglass market -- camera sweep: pitch (rows) x distance (columns). Clouds off; sprite bake is 8 deg.",
           fill=(230, 230, 230), font=small)
    for c, dist in enumerate(DIST):
        d.text((LEFT + c * (TW + PAD) + TW // 2 - 30, TOP - 28), f"{dist} m", fill=(255, 210, 120), font=big)
    missing = []
    for r, pitch in enumerate(PITCH):
        y = TOP + r * (TH + PAD)
        d.text((12, y + TH // 2 - 14), f"{pitch} deg", fill=(255, 210, 120), font=big)
        for c, dist in enumerate(DIST):
            path = os.path.join(DIR, f"p{pitch:02d}_d{dist}.png")
            x = LEFT + c * (TW + PAD)
            if not os.path.exists(path):
                missing.append(path)
                d.rectangle([x, y, x + TW, y + TH], outline=(200, 60, 60))
                continue
            sheet.paste(Image.open(path).convert("RGB").resize((TW, TH), Image.LANCZOS), (x, y))
    d.text((LEFT, H - 32), "Now in play: 22 deg in the city, 8 outside, at 20 m (1 sprite texel = 1 screen pixel only at 20 / 10 m).",
           fill=(170, 170, 170), font=small)
    out = os.path.join(DIR, "camera_sweep_sheet.png")
    sheet.save(out)
    sheet.save(out[:-4] + ".jpg", quality=90)
    print(f"wrote {out} ({W}x{H}); missing {len(missing)}")
    for m in missing:
        print("  missing", m)


if __name__ == "__main__":
    main()
