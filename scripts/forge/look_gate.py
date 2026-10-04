"""The look gate (user, 2026-09-29: "add more tests"): a capture set scored
against the city's target table, PASS / FAIL per metric, exit 1 on any FAIL.

    python D:/assests/scripts/forge/look_gate.py "D:/assests/scratch/tour_2026-09-29/roads/*.png"

The ranges are STARTING targets (memory.md, "The city is warm now"), set from
the measured references (findings 2026-09-29) and the user's calls since:
honey stone and a warm key over a cool shade; fog cut to a trace, which took
some warm share with it, so warm% is gated from 45, not the post video's 84.
Change a range here and say why in findings -- never to make a run pass.
"""
import glob
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_refs import extra  # noqa: E402
from measure import detail, load, tone  # noqa: E402

# metric: (low, high, why)
TARGETS = {
    # 2026-09-30: the city is a sunset now (the user's direction sheet, "this orangish
    # and dark"; the user picked between sweep d1 and d4). The sheet's 12 tiles:
    # mean 0.321 (0.24-0.40), dark 17.7 %, lit sat 0.401 (0.26-0.57), warm 75 %,
    # shade b* +3.5 (-0.6..+7.9). d1/d4 measured lit sat 0.61-0.63, warm 99.9 %,
    # shade b* 13-14: the user's eye chose past the sheet, so those bounds widen to
    # take the pick, and warm keeps a ceiling below 99 (the frame must still hold
    # some green and blue). The 2026-09-29 afternoon ranges are in git-less history:
    # findings 2026-09-29 and 2026-09-30.
    "mean":    (0.26, 0.38, "mean luma: the sheet 0.24-0.40; dark, with the light in pools"),
    "dark":    (8.0, 30.0, "% of pixels below 0.15 luma: the sheet 17.7; the afternoon city 8.4"),
    "litsat":  (0.34, 0.66, "colour where the light falls: sheet 0.40, the user's pick ~0.62"),
    "grey":    (0.0, 3.0, "% of near-grey pixels: 6.6 when grey; the post video 1.1"),
    # 98 -> 99.2 (user, 2026-09-30, "1 keep cobbles"): the cobbled streets of the reference
    # sheets measured 98.6 %; 99.9 (no green or blue anywhere) still fails
    "warm":    (55.0, 99.2, "% warm hues: the sheet 75; 99.9 means no green or blue anywhere"),
    "bshade":  (-4.0, 14.0, "b* of the shade: the sheet +3.5, the user's pick +13"),
    # 0.026 -> 0.034 (user, 2026-09-30, "1 keep cobbles"): cobble_hd streets measured 0.0325;
    # the cap still stops anything busier than the chosen cobbles
    "ground":  (0.0, 0.034, "ground detail: cobble_hd streets 0.0325 (user's pick); setts were 0.0268"),
}


# Per view (2026-09-30, "city life" plan): the mean hid 10 of 14 views at 99.3-99.8 % warm,
# pulled under the cap by the harbour (95.4) and farm (78.9). Bounds are the 12 sheet tiles'
# range (warm 31.6-94.7, dark 8.9-30.1, mean 0.243-0.395), widened a little for the user's
# warmer pick. Ground is printed per view, gated only on the mean.
PER_VIEW = {
    "warm": (0.0, 98.0),
    "dark": (8.0, 35.0),
    "mean": (0.24, 0.40),
}


def rows_of(files):
    rows = []
    for f in files:
        a = load(f)
        t, e = tone(a), extra(a)
        rows.append(dict(mean=t["mean"], dark=t["dark"] * 100, litsat=e["litsat"], grey=e["grey"] * 100, warm=e["warm"] * 100,
                         bshade=e["bshadow"], ground=e["ground"], detail=detail(a)))
    return rows


def score(files, rows=None):
    rows = rows or rows_of(files)
    return {k: float(np.mean([r[k] for r in rows])) for k in rows[0]}


def main(argv):
    files = sorted(f for g in argv for f in glob.glob(g))
    if not files:
        print("look_gate: no files match", argv)
        return 2
    rows = rows_of(files)
    s = score(files, rows)
    fails = 0
    for f, r in zip(files, rows):
        bad = [f"{k} {r[k]:.3f}" for k, (lo, hi) in PER_VIEW.items() if not lo <= r[k] <= hi]
        fails += bool(bad)
        print(f"{'FAIL' if bad else 'PASS'}  view {os.path.basename(f)[:30]:<30} warm {r['warm']:5.1f} dark {r['dark']:5.1f} "
              f"mean {r['mean']:.3f} ground {r['ground']:.4f}" + (f"  <- {', '.join(bad)}" if bad else ""))
    for k, (lo, hi, why) in TARGETS.items():
        ok = lo <= s[k] <= hi
        fails += not ok
        print(f"{'PASS' if ok else 'FAIL'}  {k:<7} {s[k]:8.4f}  in [{lo}, {hi}]  -- {why}")
    print(f"look_gate: {len(files)} frames, {fails} fail(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
