"""Compare the front-view silhouette of the turnaround against the sheet's.

    python D:/assests/scripts/forge/measure_silhouette.py

Plain CPython: PIL + numpy, no bpy.

Prints a width/colour profile for both images at f = 0.00, 0.05, ... 1.00 of
the figure's own height, then three PASS/FAIL checks against OURS. Exits 1 on
any FAIL.
"""
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
REF_PATH = os.path.abspath(os.path.join(HERE, "..", "..", "ref",
                                         "emberglass_player_sheet.webp"))
REF_BOX = (15, 90, 255, 470)
OURS_PATH = os.path.join(HERE, "turnaround", "player_front.png")

BG_PATCH = 20
DIFF_CUT = 38


def _bg(arr):
    corner = arr[:BG_PATCH, :BG_PATCH].reshape(-1, 3)
    return np.median(corner, axis=0)


def _mask(arr):
    bg = _bg(arr)
    diff = np.abs(arr.astype(np.int32) - bg).sum(axis=2)
    return diff > DIFF_CUT


def _hsv(rgb):
    """rgb: array [...,3] 0-255 -> (h in 0-360, s in 0-1, v in 0-1)."""
    r, g, b = rgb[..., 0] / 255.0, rgb[..., 1] / 255.0, rgb[..., 2] / 255.0
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)
    d = mx - mn
    d_safe = np.where(d == 0, 1.0, d)
    v = mx
    s = np.where(mx <= 0, 0.0, d / np.where(mx == 0, 1.0, mx))
    rmax = mx == r
    gmax = (mx == g) & ~rmax
    bmax = (~rmax) & (~gmax)
    h = np.zeros_like(mx)
    h = np.where(rmax, (60.0 * ((g - b) / d_safe)) % 360.0, h)
    h = np.where(gmax, 60.0 * ((b - r) / d_safe) + 120.0, h)
    h = np.where(bmax, 60.0 * ((r - g) / d_safe) + 240.0, h)
    h = np.where(d == 0, 0.0, h)
    return h, s, v


def profile(mask):
    rows = np.where(mask.any(axis=1))[0]
    if rows.size == 0:
        raise SystemExit("measure_silhouette: mask is empty, nothing found")
    top, bottom = int(rows.min()), int(rows.max())
    H = bottom - top + 1
    out = {}
    for i in range(21):
        f = round(i * 0.05, 2)
        row = min(top + int(round(f * (H - 1))), mask.shape[0] - 1)
        cols = np.where(mask[row])[0]
        out[f] = ((cols.max() - cols.min() + 1) / H) if cols.size else 0.0
    return out, top, H


def row_colour(arr, mask, row):
    cols_mask = mask[row]
    if not cols_mask.any():
        return "n/a"
    med = np.median(arr[row][cols_mask], axis=0).astype(int)
    return "#%02x%02x%02x" % tuple(med)


def check_face(arr, mask, top, H):
    r0 = top + int(round(0.30 * (H - 1)))
    r1 = top + int(round(0.38 * (H - 1)))
    band_mask = mask[r0:r1 + 1]
    cols = np.where(band_mask.any(axis=0))[0]
    if cols.size == 0:
        return False, None, None
    cmin, cmax = int(cols.min()), int(cols.max())
    span = cmax - cmin + 1
    c0 = cmin + int(round(span * 0.35))
    c1 = cmin + int(round(span * 0.65))
    region_mask = band_mask[:, c0:c1 + 1]
    region_rgb = arr[r0:r1 + 1, c0:c1 + 1][region_mask]
    if region_rgb.size == 0:
        return False, None, None
    h, s, _v = _hsv(region_rgb)
    hue, sat = float(np.median(h)), float(np.median(s))
    return (10.0 <= hue <= 45.0 and sat >= 0.25), hue, sat


def _load(path, box=None):
    im = Image.open(path).convert("RGB")
    if box:
        im = im.crop(box)
    return np.asarray(im, dtype=np.uint8)


def main():
    ok = True

    def check(name, cond, detail):
        nonlocal ok
        print(("PASS" if cond else "FAIL") + " " + name + ": " + detail)
        if not cond:
            ok = False

    ref_arr = _load(REF_PATH, REF_BOX)
    ours_arr = _load(OURS_PATH)

    ours_prof = ours_top = ours_H = ours_mask = None
    for label, arr in (("REF", ref_arr), ("OURS", ours_arr)):
        mask = _mask(arr)
        prof, top, H = profile(mask)
        print("-- %s %dx%d, H=%d px --" % (label, arr.shape[1], arr.shape[0], H))
        for f in sorted(prof):
            row = min(top + int(round(f * (H - 1))), mask.shape[0] - 1)
            print("  f=%.2f width=%.3f colour=%s" %
                  (f, prof[f], row_colour(arr, mask, row)))
        if label == "OURS":
            ours_prof, ours_top, ours_H, ours_mask = prof, top, H, mask

    w10 = ours_prof[0.10]
    check("crown", w10 >= 0.16,
          "OURS width@f=0.10 = %.3f (want >= 0.16, sheet 0.17)" % w10)

    flare_fs = [f for f in ours_prof if 0.45 <= f <= 0.80]
    best_f = max(flare_fs, key=lambda f: ours_prof[f])
    best_w = ours_prof[best_f]
    flare_ok = (0.50 <= best_w <= 0.56) and (0.55 <= best_f <= 0.72)
    check("flare", flare_ok,
          "OURS max width=%.3f at f=%.2f (want 0.50-0.56 at f in 0.55-0.72, "
          "sheet 0.54 @ 0.65)" % (best_w, best_f))

    face_ok, hue, sat = check_face(ours_arr, ours_mask, ours_top, ours_H)
    check("face", face_ok,
          "OURS face-row hue=%s sat=%s (want hue 10-45 deg, sat >= 0.25)" %
          ("%.1f" % hue if hue is not None else "n/a",
           "%.3f" % sat if sat is not None else "n/a"))

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
