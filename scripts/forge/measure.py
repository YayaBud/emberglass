"""Frame statistics for the game's own captures, against the reference set.

    python D:/assests/scripts/forge/measure.py [shot.png ...]

Port of `D:\\nanobanna_godot\\research\\measure.py`, pointed at this project and
with the reference numbers inlined so it runs without the 101 reference JPEGs
(which live in nanobanna and are not duplicated here).

Five things, because they are what the eye reads first and they are the five the
audit measured every reference game on:

    mean   average luminance
    dk%    share of pixels below 0.15 luma -- the single biggest difference
           between an HD-2D frame and a flat one
    sat    average saturation
    detail mean absolute gradient, i.e. how much local texture there is
    profile gradient energy in six horizontal bands, normalised -- the
           tilt-shift signature: references peak in bands 3-4 and fall at both
           ends

Every frame is resampled to 640x360 first, so "detail" means detail per pixel of
a render target, not per pixel of whatever the window happened to be.
"""
import glob
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.abspath(os.path.join(HERE, "..", "..", "game"))

# Targets, from hd2d_foundation_audit.md section 11. Quoted, not re-measured:
# the reference frames live in nanobanna.
TARGET = {
    "mean": (0.30, 0.40),
    "dark": (0.20, 1.00),
    # 2026-09-27: the user's reference videos (0.19-0.48); HD-2D's 0.45-0.52
    # could not hold once the city sun went to 5000 K on the user's call
    "sat": (0.30, 0.50),
    # 2026-09-27: an UPPER bound now. The user picked the calm look of four
    # reference videos over HD-2D's dense texture (memory.md "Calm and palette").
    "detail": (0.0, 0.035),
}
# What each reference game measured, for context in the printout.
REFERENCE = {
    "octopath1": (0.324, 0.316, 0.482, 0.0256),
    "octopath2": (0.286, 0.435, 0.497, 0.0314),
    "dq3": (0.388, 0.157, 0.522, 0.0266),
    "liveal": (0.270, 0.409, 0.560, 0.0306),
    "triangle": (0.292, 0.368, 0.481, 0.0342),
}


def load(path):
    return (np.asarray(Image.open(path).convert("RGB").resize((640, 360), Image.LANCZOS))
            .astype(np.float32) / 255.0)


def tone(a):
    lum = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    return dict(mean=float(lum.mean()), dark=float((lum < 0.15).mean()),
                bright=float((lum > 0.75).mean()), sat=float(sat.mean()))


def detail(a):
    g = 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
    return float((np.abs(np.diff(g, axis=1)).mean()
                  + np.abs(np.diff(g, axis=0)).mean()) / 2)


def profile(a, bands=6):
    g = np.abs(np.diff(0.2126 * a[..., 0] + 0.7152 * a[..., 1]
                       + 0.0722 * a[..., 2], axis=1))
    h = 360 // bands
    v = np.array([g[i * h:(i + 1) * h].mean() for i in range(bands)])
    return v / max(v.mean(), 1e-9)


def mark(value, lo, hi):
    return "ok  " if lo <= value <= hi else "MISS"


def main(paths):
    if not paths:
        paths = sorted(glob.glob(os.path.join(GAME, "shot_*.png")))
    paths = [p for p in paths if os.path.exists(p)]
    if not paths:
        print("no shots found in " + GAME)
        return 1

    print(f"{'frame':<22}{'mean':>6}{'dk%':>7}{'sat':>7}{'detail':>8}   "
          "sharpness top->bottom")
    rows = []
    for p in paths:
        a = load(p)
        t = tone(a)
        d = detail(a)
        pr = profile(a)
        rows.append((t, d))
        print(f"{os.path.basename(p):<22}{t['mean']:6.3f}{t['dark']*100:7.1f}"
              f"{t['sat']:7.3f}{d:8.4f}   " + " ".join(f"{x:4.2f}" for x in pr))

    print()
    for name, (m, dk, s, de) in REFERENCE.items():
        print(f"  ref {name:<18}{m:6.3f}{dk*100:7.1f}{s:7.3f}{de:8.4f}")

    print()
    mean = float(np.mean([t["mean"] for t, _ in rows]))
    dark = float(np.mean([t["dark"] for t, _ in rows]))
    sat = float(np.mean([t["sat"] for t, _ in rows]))
    det = float(np.mean([d for _, d in rows]))
    print("OURS, averaged over %d frames, against the targets:" % len(rows))
    print(f"  mean luminance  {mean:6.3f}  target {TARGET['mean']}      {mark(mean, *TARGET['mean'])}")
    print(f"  pixels < 0.15   {dark*100:5.1f}%  target >= 20%          {mark(dark, *TARGET['dark'])}")
    print(f"  saturation      {sat:6.3f}  target {TARGET['sat']}      {mark(sat, *TARGET['sat'])}")
    print(f"  detail density  {det:6.4f}  target <= 0.035       {mark(det, *TARGET['detail'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
