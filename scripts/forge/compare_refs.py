"""Our captures against the four videos the user sent (2026-09-27), with the
project's own metrics (measure.py) plus value contrast, the warm/cool split and
ground noise.

    python D:/assests/scripts/forge/compare_refs.py

Frames: ref/videos_2026-09-27/<name>/ (made by video_frames.py through
Blender's sequencer -- there is no ffmpeg on this machine). Ours: the game's
shot_folk_*.png from `--camtest --folkshots`.

    detail / ground   mean |gradient|, whole frame / bottom third (texture noise)
    L*spread          L* p90 - p10 (value contrast)
    b*shade / b*lit   CIELAB b* of the darkest / lightest quarter (+ = yellow)
    cool% / warm%     pixels with saturation > 0.2 and hue 150-270 / <60 or >330
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure import detail, load, tone  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
REF = os.path.join(ROOT, "ref", "videos_2026-09-27")


def lab(a):
    # sRGB -> CIELAB (D65), standard formulas
    c = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    x = (c @ np.array([0.4124, 0.3576, 0.1805])) / 0.95047
    y = c @ np.array([0.2126, 0.7152, 0.0722])
    z = (c @ np.array([0.0193, 0.1192, 0.9505])) / 1.08883
    f = lambda t: np.where(t > 0.008856, np.cbrt(t), 7.787 * t + 16 / 116)
    fx, fy, fz = f(x), f(y), f(z)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def extra(a):
    L, A, B = lab(a)
    lo, hi = np.percentile(L, 25), np.percentile(L, 75)
    mx, mn = a.max(2), a.min(2)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    d = np.maximum(mx - mn, 1e-6)
    h = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    col = sat > 0.2
    cool = float((col & (h >= 150) & (h <= 270)).mean())
    warm = float((col & ((h < 60) | (h > 330))).mean())
    ground = detail(a[240:])   # bottom third: mostly ground in a raised camera
    top = L[:120]              # top third: sky / far distance, where haze flattens value
    lum = a @ np.array([0.2126, 0.7152, 0.0722])
    lit = lum > np.percentile(lum, 60)   # the lit 40 %: where colour reads (2026-09-29, "all grey")
    return dict(spread=float(np.percentile(L, 90) - np.percentile(L, 10)),
                haze=float(np.percentile(top, 90) - np.percentile(top, 10)),
                grey=float((sat < 0.12).mean()), litsat=float(sat[lit].mean()),
                bshadow=float(B[L <= lo].mean()), blit=float(B[L >= hi].mean()),
                cool=cool, warm=warm, ground=ground)


def pick(pattern, keep=None):
    fs = sorted(glob.glob(os.path.join(ROOT, pattern)))
    return fs if keep is None else [fs[i] for i in keep]


# All nine reference videos (2026-09-29). Frames dropped by index are menus, card screens,
# black cuts and duplicates, chosen by eye from a contact sheet. The A/B video is portrait
# (with post on top, without below); each half is centre-cropped to 16:9.
def main():
    global groups
    groups = {
        "OURS city (3)": pick("game/shot_city_*_now.png"),
        "OURS biomes (5)": pick("game/shot_bio_*.png"),
        "forest_river": pick("ref/videos_2026-09-27/forest_river/f*.jpg"),
        "beach_daynight": pick("ref/videos_2026-09-27/beach_daynight/f*.jpg"),
        "topdown_fishing": pick("ref/videos_2026-09-27/topdown_fishing/f*.jpg"),
        "inkwash_combat": pick("ref/videos_2026-09-27/inkwash_combat/f*.jpg")[1:],  # f00 is a blurred intro
        "pp_with": pick("ref/video_2026-09-28/pp_with/f*.jpg"),
        "pp_without": pick("ref/video_2026-09-28/pp_without/f*.jpg"),
        "new_1": pick("ref/videos_2026-09-29/new_1_frames/*.jpg", [1, 2, 3, 4, 6, 7]),
        "new_2": pick("ref/videos_2026-09-29/new_2_frames/*.jpg"),
        "dq3": pick("ref/yt_downloads/dq3_frames/*", [0, 1, 2, 5, 8, 9, 11]),
        "octopath2": pick("ref/yt_downloads/octopath2_frames/*", [1, 3, 4, 6, 7, 8, 10]),
    }

    # `compare_refs.py "game/shot_grade_c1_*.png" ...`: score those shot sets instead
    # (one row per glob), e.g. the `--gradesweep` candidates
    if sys.argv[1:]:
        groups = {os.path.join(os.path.basename(os.path.dirname(g)), os.path.basename(g)): sorted(glob.glob(g)) for g in sys.argv[1:]}

    print(f"{'group':<22}{'mean':>6}{'dk%':>6}{'sat':>6}{'detail':>8}{'ground':>8}{'L*spread':>9}"
          f"{'b*shade':>8}{'b*lit':>7}{'cool%':>7}{'warm%':>7}{'haze':>6}{'grey%':>6}{'litsat':>7}")
    for name, fs in groups.items():
        rows = []
        for f in fs:
            a = load(f)
            t = tone(a)
            e = extra(a)
            rows.append([t["mean"], t["dark"] * 100, t["sat"], detail(a), e["ground"], e["spread"],
                         e["bshadow"], e["blit"], e["cool"] * 100, e["warm"] * 100, e["haze"], e["grey"] * 100, e["litsat"]])
        m, lo, hi = np.mean(rows, axis=0), np.min(rows, axis=0), np.max(rows, axis=0)
        print(f"{name:<22}{m[0]:6.3f}{m[1]:6.1f}{m[2]:6.3f}{m[3]:8.4f}{m[4]:8.4f}{m[5]:9.1f}"
              f"{m[6]:8.1f}{m[7]:7.1f}{m[8]:7.1f}{m[9]:7.1f}{m[10]:6.1f}{m[11]:6.1f}{m[12]:7.3f}   n={len(fs)}")
        # the spread over the group's frames: targets are ranges, not the mean
        print(f"{'  min':<22}{lo[0]:6.3f}{lo[1]:6.1f}{lo[2]:6.3f}{lo[3]:8.4f}{lo[4]:8.4f}{lo[5]:9.1f}"
              f"{lo[6]:8.1f}{lo[7]:7.1f}{lo[8]:7.1f}{lo[9]:7.1f}{lo[10]:6.1f}{lo[11]:6.1f}{lo[12]:7.3f}")
        print(f"{'  max':<22}{hi[0]:6.3f}{hi[1]:6.1f}{hi[2]:6.3f}{hi[3]:8.4f}{hi[4]:8.4f}{hi[5]:9.1f}"
              f"{hi[6]:8.1f}{hi[7]:7.1f}{hi[8]:7.1f}{hi[9]:7.1f}{hi[10]:6.1f}{hi[11]:6.1f}{hi[12]:7.3f}")


if __name__ == "__main__":
    main()
