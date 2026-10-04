"""Lighting study: the same two frames under many lights, each one measured.

    python D:/assests/scripts/forge/light_study.py            # render what is missing, measure, sheets
    python D:/assests/scripts/forge/light_study.py --force    # re-render everything
    python D:/assests/scripts/forge/light_study.py --refs     # measure the reference set only

Every variant is the game's own `--light=` spec (Grade.Tune), so any tile can
be walked around in: `Godot --path game -- --light=golden,lift:0.5`.

Two views: `road` is the spawn, looking down the village road; `mid` stands 28 m
further along it. Output in `renders/light_study/`: one PNG per render, one
contact sheet per series, and `results.md`.

The time-of-day presets are exposed like a camera would be before they are
compared -- up to two correction steps toward a target mean, because a midday
frame at dusk exposure is blown out and a night frame is black, and neither
tells you anything about the light. Those targets are picked, not measured
(TARGET_MEAN). The single-dial series keep the shipped exposure, so a dial's
effect on brightness stays visible.

Warmth is new here, measured the same way on our frames and on the 101
reference frames: CIELAB b* (yellow +, blue -) of the brightest and darkest
fifth of pixels, in the bottom 60% of the frame so the sky mostly stays out.
`split` = lit b* - shade b*: how strongly warm light sits against cool shadow.
"""
import glob
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import measure  # noqa: E402  (load, tone, detail)

GODOT = "D:/tools/Godot_v4.6.3-stable_mono_win64/Godot_v4.6.3-stable_mono_win64_console.exe"
GAME = "D:/assests/game"
OUT = "D:/assests/renders/light_study"
REFS = "D:/nanobanna_godot/research/refs"
GAMES = ["octopath1", "octopath2", "triangle", "dq3", "liveal", "sacrifire", "replaced", "eiyuden", "anno"]

# Village path space: a runs down the road along F = (-0.7071, -0.7071) in (x, z).
VIEWS = {"road": [], "mid": ["--at=-19.8,-19.8"]}

SHIPPED_EXPOSURE = 0.90
# Picked, not measured: the reference band is 0.175-0.39 (audit section 5).
TARGET_MEAN = {"golden": 0.30, "late": 0.30, "afternoon": 0.34, "midday": 0.36,
               "bluehour": 0.22, "night": 0.16, "overcast": 0.36}

ALL = "grain:1,bloom:1,vfog:0.003,gi:both,tone:aces"
BLUE = "bluehour,exp:1.175"   # the exposure the time-of-day series calibrated

SERIES = [
    ("time of day (each exposed to its own target mean)", "time", [
        ("golden 5deg", "golden"), ("late 14deg (shipped)", "late"),
        ("afternoon 32deg", "afternoon"), ("midday 60deg", "midday"),
        ("blue hour", "bluehour"), ("night", "night"), ("overcast", "overcast")]),
    ("warmth: sun colour temperature", "warmth", [
        ("2500K", "k:2500"), ("3000K", "k:3000"), ("shipped ~3600K", ""),
        ("4500K", "k:4500"), ("5500K", "k:5500"), ("6500K", "k:6500")]),
    ("shadow depth: ambient + fill energy", "depth", [
        ("x0.25", "lift:0.25"), ("x0.5", "lift:0.5"), ("shipped", ""),
        ("x1.6", "lift:1.6"), ("x2.5", "lift:2.5")]),
    ("shadow colour (same luminance)", "shade", [
        ("blue (shipped)", ""), ("violet", "shade:violet"), ("teal", "shade:teal"),
        ("grey", "shade:grey"), ("warm", "shade:warm")]),
    ("sun direction", "direction", [
        ("backlit (shipped)", ""), ("back-side", "yaw:-95"),
        ("side", "yaw:-45"), ("front", "yaw:32")]),
    ("shadow softness (sun size, PCSS)", "soft", [
        ("hard (shipped)", ""), ("1.5 deg", "soft:1.5"), ("4 deg", "soft:4")]),
    ("lamps and windows", "lamps", [
        ("off", "lamps:0"), ("shipped", ""), ("x2", "lamps:2"), ("x3.5", "lamps:3.5")]),
    # What the references have that the shipped frame does not, one at a time.
    ("renderer features the references use, at the shipped dusk", "feat", [
        ("shipped", ""), ("+ texture proxy", "grain:1"), ("+ bloom", "bloom:1"),
        ("+ vol. fog 0.002", "vfog:0.002"), ("+ vol. fog 0.005", "vfog:0.005"), ("+ SSIL bounce", "gi:ssil"),
        ("+ SDFGI bounce", "gi:sdfgi"), ("+ ACES", "tone:aces"), ("+ AgX", "tone:agx"),
        ("all (ACES)", ALL)]),
    ("the same at blue hour, where lamps can pool", "featblue", [
        ("blue hour", BLUE), ("blue hour, all", f"{BLUE},{ALL}"),
        ("blue hour, all, lamps x2", f"{BLUE},{ALL},lamps:3.6")]),
]


def slug(spec):
    return (spec or "base").replace(":", "").replace(",", "_").replace(".", "p")


def render(spec, view, force):
    path = f"{OUT}/{slug(spec)}__{view}.png"
    if os.path.exists(path) and not force:
        return path
    args = [GODOT, "--path", GAME, "--", f"--shot={path}", "--frames=90"] + VIEWS[view]
    if spec:
        args.append("--light=" + spec)
    r = subprocess.run(args, capture_output=True, text=True, timeout=240)
    log = r.stdout + r.stderr
    if "--light:" in log or not os.path.exists(path):
        raise RuntimeError(f"render failed: {spec!r} {view}\n{log[-3000:]}")
    print(f"  rendered {slug(spec)}__{view}", flush=True)
    return path


def lab(a):
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = lin @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return 116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])


def stats(path):
    a = measure.load(path)
    t = measure.tone(a)
    L, A, B = (c[144:] for c in lab(a))   # bottom 60% of 360 rows
    # Near-black carries no hue to read, and letterbox bars and the vignette
    # floor are near-black. Percentiles over what is left: taken over the whole
    # band, a frame more than a fifth black left the shade set EMPTY and
    # reported a neutral 0.0 that was never measured.
    Lv = L[L > 5]
    hi = L >= np.percentile(Lv, 80)
    lo = (L > 5) & (L <= np.percentile(Lv, 20))
    s = dict(mean=t["mean"], dark=t["dark"], sat=t["sat"], detail=measure.detail(a),
             b_lit=float(B[hi].mean()), b_shade=float(B[lo].mean()),
             a_shade=float(A[lo].mean()),
             contrast=float(np.percentile(Lv, 90) - np.percentile(Lv, 10)))
    s["split"] = s["b_lit"] - s["b_shade"]
    return s


def calibrate(preset, force):
    """Exposure for `preset` that lands the road view near its target mean.
    Assumes mean ~ exposure^0.5 for the first step, then measures the exponent."""
    target, e, g = TARGET_MEAN[preset], SHIPPED_EXPOSURE, 0.5
    m = stats(render(preset, "road", force))["mean"]
    for _ in range(2):
        if abs(m / target - 1) < 0.04:
            break
        e2 = float(np.clip(e * (target / m) ** (1 / g), 0.1, 8.0))
        m2 = stats(render(f"{preset},exp:{e2:.3f}", "road", force))["mean"]
        if abs(np.log(e2 / e)) > 1e-3 and m2 > 0 and m > 0:
            g = float(np.clip(np.log(m2 / m) / np.log(e2 / e), 0.15, 1.5))
        e, m = e2, m2
    return (preset if e == SHIPPED_EXPOSURE else f"{preset},exp:{e:.3f}"), e


def ref_stats():
    rows = {}
    for game in GAMES:
        files = sorted(glob.glob(f"{REFS}/{game}_*.jpg"))
        per = [stats(f) for f in files]
        rows[game] = {k: float(np.mean([p[k] for p in per])) for k in per[0]} | {"n": len(files)}
    return rows


COLS = ["mean", "dark", "sat", "b_lit", "b_shade", "split", "a_shade", "contrast"]


def fmt(s):
    return (f"{s['mean']:.3f} | {s['dark'] * 100:.1f} | {s['sat']:.3f} | {s['b_lit']:+.1f} | "
            f"{s['b_shade']:+.1f} | {s['split']:+.1f} | {s['a_shade']:+.1f} | {s['contrast']:.1f}")


def font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def sheet(title, items, path):
    tw, th, pad, lab_h, head = 400, 225, 6, 52, 34
    img = Image.new("RGB", (pad + len(items) * (tw + pad), head + len(VIEWS) * (th + lab_h + pad)),
                    (18, 18, 22))
    d = ImageDraw.Draw(img)
    d.text((pad, 8), title, fill=(236, 236, 236), font=font(18))
    for c, (label, pngs, st, _) in enumerate(items):
        for r, view in enumerate(VIEWS):
            x, y = pad + c * (tw + pad), head + r * (th + lab_h + pad)
            img.paste(Image.open(pngs[view]).convert("RGB").resize((tw, th), Image.LANCZOS), (x, y))
            s = st[view]
            d.text((x, y + th + 3), f"{label}   [{view}]", fill=(240, 220, 160), font=font(14))
            d.text((x, y + th + 20), f"mean {s['mean']:.2f}   dark {s['dark'] * 100:.0f}%   "
                                     f"sat {s['sat']:.2f}", fill=(210, 210, 210), font=font(13))
            d.text((x, y + th + 35), f"lit b* {s['b_lit']:+.0f}   shade b* {s['b_shade']:+.0f}   "
                                     f"split {s['split']:+.0f}", fill=(210, 210, 210), font=font(13))
    img.save(path, quality=92)


def main(argv):
    force = "--force" in argv
    os.makedirs(OUT, exist_ok=True)

    refs = ref_stats()
    md = ["# Lighting study", "",
          "Generated by `scripts/forge/light_study.py`. Warmth columns are CIELAB over the",
          "bottom 60% of the frame: b* of the brightest / darkest fifth of pixels, split =",
          "lit - shade, a* of the shade (+ magenta, - green), contrast = L* p90 - p10.", "",
          "## Reference set (mean of each game's frames)", "",
          "| game | n | mean | dark% | sat | lit b* | shade b* | split | shade a* | contrast |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for game, s in refs.items():
        md.append(f"| {game} | {s['n']} | {fmt(s)} |")
    band = {k: (min(s[k] for s in refs.values()), max(s[k] for s in refs.values())) for k in COLS}
    md.append("| **range** | | " + " | ".join(
        f"{lo * 100:.1f}-{hi * 100:.1f}" if k == "dark" else f"{lo:+.1f}-{hi:+.1f}"
        if k in ("b_lit", "b_shade", "split", "a_shade") else f"{lo:.2f}-{hi:.2f}"
        for k, (lo, hi) in band.items()) + " |")
    if "--refs" in argv:
        print("\n".join(md))
        return 0

    for title, key, variants in SERIES:
        print(f"{key}:", flush=True)
        items = []
        for label, spec in variants:
            exp = SHIPPED_EXPOSURE
            if key == "time":
                spec, exp = calibrate(spec, force)
            pngs = {v: render(spec, v, force) for v in VIEWS}
            items.append((label, pngs, {v: stats(p) for v, p in pngs.items()}, (spec, exp)))
        sheet(title, items, f"{OUT}/sheet_{key}.jpg")
        md += ["", f"## {title}", "", "Sheet: `sheet_" + key + ".jpg`", "",
               "| variant | spec | exposure | view | mean | dark% | sat | lit b* | shade b* | split | shade a* | contrast |",
               "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for label, _, st, (spec, exp) in items:
            for v in VIEWS:
                md.append(f"| {label} | `{spec or '(none)'}` | {exp:.2f} | {v} | {fmt(st[v])} |")

    with open(f"{OUT}/results.md", "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    print(f"wrote {OUT}/results.md")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
