"""Snow-biome lighting sweep: many grades of the Hoarfells, each measured
against the user's snow-region reference frame.

    python D:/assests/scripts/forge/snow_sweep.py            # round 1: one dial at a time + looks
    python D:/assests/scripts/forge/snow_sweep.py --combine  # round 2: best of each dial together

Every candidate is a `--snowlight=` spec (Grade.TuneSnow dials; since the
round-2 pick was adopted they apply over Grade.SnowSwept, so a rerun of
round 1 now sweeps around the shipped grade), rendered in ONE game launch (`--sweep=`) standing on the lamp
walk (SnowSite.Vista), clear weather, snow depth 0.8. Measured with the
lighting study's own `stats()` (mean, dark share, saturation, L* contrast,
b* of the lit and shaded fifths and their split) on the frame minus its
bottom 15% (the reference's caption band), and scored as the summed distance
to the reference in fixed units (SCALE). Writes renders/snow_sweep/: the
frames, sheet_<round>.png, results_<round>.json/.md.

The reference is one frame, so the score says "closer to that frame", not
"better". The scales are picked, not measured.
"""
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import light_study  # noqa: E402  (stats, lab)

GODOT = light_study.GODOT
GAME = light_study.GAME
ROOT = "D:/assests"
OUT = f"{ROOT}/renders/snow_sweep"
REF = f"{ROOT}/ref/snow_region.png"
VISTA = "--at=-404.9,451.9"

SCALE = dict(mean=0.03, dark=0.05, sat=0.04, contrast=5.0, b_lit=3.0, b_shade=3.0, split=3.0)

# (group, name, dials over Grade.SnowLight)
ROUND1 = [
    ("base", "base", ""),
    ("k", "k2600", "k:2600"), ("k", "k3400", "k:3400"), ("k", "k6500", "k:6500"),
    ("sun", "sun0.6", "sun:0.6"), ("sun", "sun2.0", "sun:2.0"), ("sun", "sun3.0", "sun:3.0"),
    ("elev", "elev8", "elev:8"), ("elev", "elev30", "elev:30"),
    ("yaw", "yaw-90", "yaw:-90"), ("yaw", "yaw-135", "yaw:-135"),
    ("lamps", "lamps3", "lamps:3"), ("lamps", "lamps9", "lamps:9"), ("lamps", "lamps14", "lamps:14"),
    ("shade", "violet", "shade:violet"), ("shade", "teal", "shade:teal"), ("shade", "grey", "shade:grey"),
    ("lift", "lift0.6", "lift:0.6"), ("lift", "lift1.5", "lift:1.5"),
    ("fog", "fog_lo", "fogd:0.4,vfog:0.0015"), ("fog", "fog_hi", "fogd:2.5,vfog:0.008"),
    ("fogw", "fogw0.4", "fogw:0.4"), ("fogw", "fogw0.8", "fogw:0.8"),
    ("exp", "exp0.85", "exp:0.85"), ("exp", "exp1.3", "exp:1.3"),
    ("sat", "sat0.6", "sat:0.6"), ("sat", "sat0.9", "sat:0.9"),
    ("look", "warm_dusk", "k:2800,sun:2.2,elev:9,lamps:8,fogw:0.35"),
    ("look", "lantern_night", "sun:0.4,k:6000,lamps:12,lift:0.8,exp:1.2"),
    ("look", "bright_day", "k:5800,sun:3.0,elev:30,exp:0.95,fogd:0.5"),
    ("look", "cold_blue", "k:7000,sun:1.0,shade:blue,sat:0.6"),
]


# Round 3 (after the kit dressed the lamp walk): brightness. The shipped
# grade measured mean 0.512 against the reference's 0.313 (findings).
ROUND3 = [
    ("base", "r3_base", ""),
    ("exp", "exp0.45", "exp:0.45"), ("exp", "exp0.55", "exp:0.55"), ("exp", "exp0.65", "exp:0.65"), ("exp", "exp0.75", "exp:0.75"),
    ("mix", "e60_lamps6", "exp:0.6,lamps:6"), ("mix", "e60_grey", "exp:0.6,shade:grey"), ("mix", "e60_lift", "exp:0.6,lift:0.7"),
    ("mix", "e55_sun", "exp:0.55,sun:0.5"), ("mix", "e65_fog", "exp:0.65,fogd:1.6"), ("mix", "e60_sat", "exp:0.6,sat:0.95"),
    ("mix", "e50_lamps11", "exp:0.5,lamps:11"),
]


# Round 4: round 3's best (exposure + fog) with the lanterns tamed -- their
# pools blew out (bright b* went warm-positive, contrast 82-86 vs 48.9).
ROUND4 = [
    ("keep", "r4_e65_fog", "exp:0.65,fogd:1.6"),
    ("mix", "r4_e65_fog_l4", "exp:0.65,fogd:1.6,lamps:4"),
    ("mix", "r4_e70_fog_l3", "exp:0.7,fogd:1.6,lamps:3"),
    ("mix", "r4_e60_fog_l4", "exp:0.6,fogd:1.8,lamps:4"),
]


# Round 5 (user on round 4's look: "just too much brightness"): the same
# grade darker, on round 3's exposure curve (0.45 -> mean 0.315).
ROUND5 = [
    ("exp", "r5_e52", "exp:0.52,fogd:1.6,lamps:3"),
    ("exp", "r5_e58", "exp:0.58,fogd:1.6,lamps:3"),
]


def walk_at(d):
    """SnowSite.WalkAt: a point d metres down the lamp walk (world x, z)."""
    c = (-430.0, 430.0)
    pts = [(34, 30), (12, 10), (-10, -12), (-38, -36)]
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        L = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
        if d <= L or (bx, bz) == pts[-1]:
            t = min(d, L) / L
            return c[0] + ax + (bx - ax) * t, c[1] + az + (bz - az) * t
        d -= L


def path_at(pts, d):
    """SnowSite.PathAt over offsets from the region centre."""
    c = (-430.0, 430.0)
    for (ax, az), (bx, bz) in zip(pts, pts[1:]):
        L = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
        if d <= L or (bx, bz) == pts[-1]:
            t = min(d, L) / L
            return "{:.1f},{:.1f}".format(c[0] + ax + (bx - ax) * t, c[1] + az + (bz - az) * t)
        d -= L


PASS = [(90, -30), (68, -52), (45, -75)]
VILLAGE = [(-30, 58), (-52, 36), (-74, 14)]
RUINS = [(0, -58), (-22, -80), (-44, -102)]
WALK = [(34, 30), (12, 10), (-10, -12), (-38, -36)]
# The sheet's five scenes and its four atmospheres (looks by name), one launch.
TOUR2 = [
    ("scene", "s1_forest_path", "", path_at(WALK, 12)),
    ("scene", "s2_mountain_pass", "", path_at(PASS, 6)),
    ("scene", "s3_village", "", path_at(VILLAGE, 6)),
    ("scene", "s4_cliff_edge", "", path_at(WALK, 84)),
    ("scene", "s5_ruins", "", path_at(RUINS, 6)),
]

# The tour: the shipped grade from several places on the lamp walk, to see
# the kit's props and the ground tiles in frame (one launch).
TOUR = [("tour", f"tour_d{d}", "", "{:.1f},{:.1f}".format(*walk_at(d))) for d in (12, 26, 48, 66, 96)]


def crop_stats(path):
    """stats() on the frame without its bottom 15% (the reference's caption)."""
    im = Image.open(path).convert("RGB")
    w, h = im.size
    tmp = path + ".crop.png"
    im.crop((0, 0, w, int(h * 0.85))).save(tmp)
    s = light_study.stats(tmp)
    os.remove(tmp)
    return s


def score(s, ref):
    return float(sum(abs(s[k] - ref[k]) / v for k, v in SCALE.items()))


def launch(specs, tag):
    os.makedirs(OUT, exist_ok=True)
    spec_file = f"{OUT}/specs_{tag}.txt"
    with open(spec_file, "w") as fh:
        fh.write("\n".join("|".join(sp[1:]) for sp in specs))
    # always on top: a minimised or covered window stops drawing, and every
    # frame after that is the same stale image (round 2's first try, 2026-09-23)
    args = [GODOT, "--always-on-top", "--path", GAME, "--", VISTA, "--weather=clear", "--snow=0.8",
            f"--sweep={spec_file},{OUT}"]
    run = subprocess.run(args, capture_output=True, text=True, timeout=900)
    log = run.stdout
    # keep the whole log: a stall (identical frames) is diagnosed from it
    with open(f"{OUT}/log_{tag}.txt", "w", encoding="utf-8") as fh:
        fh.write(run.stdout + "\n--- stderr ---\n" + run.stderr)
    done = [ln for ln in log.splitlines() if ln.startswith("sweep:")]
    print(f"launch {tag}: {len(done)} of {len(specs)} frames", flush=True)
    if len(done) != len(specs):
        raise RuntimeError(log[-3000:])


def sheet(rows, path):
    tw, th = 320, 180
    cols = 4
    img = Image.new("RGB", (cols * tw, ((len(rows) + cols - 1) // cols) * (th + 18)), (20, 20, 24))
    d = ImageDraw.Draw(img)
    for i, r in enumerate(rows):
        x, y = (i % cols) * tw, (i // cols) * (th + 18)
        img.paste(Image.open(f"{OUT}/{r['name']}.png").convert("RGB").resize((tw, th)), (x, y))
        d.text((x + 4, y + th + 2), f"{i + 1}. {r['name']}  {r['score']:.2f}", fill=(230, 230, 230))
    img.save(path)


def report(rows, ref, tag):
    rows.sort(key=lambda r: r["score"])
    with open(f"{OUT}/results_{tag}.json", "w") as fh:
        json.dump(dict(ref=ref, rows=rows), fh, indent=1)
    lines = [f"# Snow sweep, round {tag}", "",
             "reference: " + light_study.fmt(ref), "",
             "| # | name | dials | score | mean | dark% | sat | b lit | b shade | split | a shade | contrast |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows):
        lines.append(f"| {i + 1} | {r['name']} | `{r['dials']}` | {r['score']:.2f} | " + light_study.fmt(r["stats"]) + " |")
    open(f"{OUT}/results_{tag}.md", "w").write("\n".join(lines) + "\n")
    sheet(rows, f"{OUT}/sheet_{tag}.png")
    for r in rows[:6]:
        print(f"  {r['score']:6.2f}  {r['name']:<14} {r['dials']}")


def measure(specs, ref):
    import hashlib
    seen = {}
    for sp in specs:
        n = sp[1]
        h = hashlib.md5(open(f"{OUT}/{n}.png", "rb").read()).hexdigest()
        if h in seen:
            raise RuntimeError(f"{n} is byte-identical to {seen[h]}: the game stopped drawing")
        seen[h] = n
    rows = []
    for sp in specs:
        g, n, d = sp[:3]
        s = crop_stats(f"{OUT}/{n}.png")
        rows.append(dict(group=g, name=n, dials=d, stats=s, score=score(s, ref)))
    return rows


def main(argv):
    ref = crop_stats(REF)
    print("reference:", light_study.fmt(ref))
    if "--looks" in argv:
        # one short launch per look: in one sweep, every frame after the first
        # look change came out byte-identical (tour 2, twice; cause not found)
        for name in ("clear", "overcast", "snowfall", "sunset"):
            out = f"{OUT}/a_{name}.png"
            subprocess.run([GODOT, "--always-on-top", "--path", GAME, "--", "--at=" + path_at(WALK, 12),
                            "--weather=clear", "--snow=0.8", f"--snowlook={name}", "--frames=300", f"--shot={out}"],
                           capture_output=True, text=True, timeout=300)
            print(name, light_study.fmt(crop_stats(out)))
        return 0
    if "--tour2" in argv:
        launch(TOUR2, "tour2")
        report(measure(TOUR2, ref), ref, "tour2")
        return 0
    if "--tour" in argv:
        launch(TOUR, "tour")
        report(measure(TOUR, ref), ref, "tour")
        return 0
    if "--round5" in argv:
        launch(ROUND5, "5")
        report(measure(ROUND5, ref), ref, "5")
        return 0
    if "--round4" in argv:
        launch(ROUND4, "4")
        report(measure(ROUND4, ref), ref, "4")
        return 0
    if "--round3" in argv:
        launch(ROUND3, "3")
        report(measure(ROUND3, ref), ref, "3")
        return 0
    if "--combine" not in argv:
        launch(ROUND1, "1")
        report(measure(ROUND1, ref), ref, "1")
        return 0
    r1 = json.load(open(f"{OUT}/results_1.json"))["rows"]
    base = next(r for r in r1 if r["name"] == "base")["score"]
    best = {}
    for r in r1:
        if r["group"] in ("base", "look") or r["score"] >= base:
            continue
        if r["group"] not in best or r["score"] < best[r["group"]]["score"]:
            best[r["group"]] = r
    combined = ",".join(r["dials"] for r in sorted(best.values(), key=lambda r: r["score"]))
    top = sorted(r1, key=lambda r: r["score"])
    specs = [("combo", "combo_all", combined)]
    # the combination without its weakest dial too: dials interact
    if len(best) > 1:
        specs.append(("combo", "combo_top", ",".join(r["dials"] for r in sorted(best.values(), key=lambda r: r["score"])[:-1])))
    specs += [("keep", "r1_" + r["name"], r["dials"]) for r in top[:2]]
    # the reference's own look, by eye: warm lanterns in a cool dusk
    specs += [("base", "base", ""),
              ("look", "lantern_dusk", "exp:0.85,sun:0.8,k:3000,elev:10,yaw:-100,lamps:9,fogw:0.5,shade:blue,sat:0.85"),
              ("look", "lantern_cool", "exp:0.9,sun:0.5,k:5200,lamps:10,fogw:0.3,lift:0.8,sat:0.8,fogd:1.5")]
    launch(specs, "2")
    report(measure(specs, ref), ref, "2")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
