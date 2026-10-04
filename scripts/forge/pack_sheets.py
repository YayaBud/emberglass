"""Raw Blender frames -> pixel art -> packed strips + the manifest the game reads.

    python D:/assests/scripts/forge/pack_sheets.py

Three things happen here, in this order, and the order matters:

1. DOWNSCALE. The raw frame is 64 px already, so this is a no-op today, but the
   hook stays: rendering at 2x and boxing down is the standard way to buy a
   cleaner silhouette, and the code should not have to change to do it.
2. QUANTISE to the ten swatches in `player_palette.py`. EEVEE's shading spreads
   each swatch across dozens of near-identical values; left alone they survive
   into the sheet and the figure stops reading as pixel art. Nearest swatch in
   linear space, because nearest in sRGB pulls every shadow toward black.
3. OUTLINE. One pixel of near-black around the silhouette. This is what makes a
   48 px character the highest-contrast object in the frame (Law 6) -- without
   it the green tunic sits on green grass and the player is lost.

Alpha is binary throughout: the game renders these with alpha-scissor, so a
half-transparent edge pixel would show as a hard fringe anyway.

Plain CPython. Does not import bpy.
"""
import json
import os
import sys
from collections import defaultdict

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from player_palette import ORDER, SHADES, SWATCHES, srgb8, srgb_to_linear  # noqa: E402

RAW = os.path.join(HERE, "raw")
OUT = os.path.join(HERE, "..", "..", "game", "assets", "sprites")
OUT = os.path.abspath(OUT)

CANVAS_PX = 128
SPRITE_PX = 96
BAKE_DEG = 8.0
WORLD_H = 1.85
ALPHA_CUT = 128          # below this the pixel is simply not there
OUTLINE = (23, 22, 28)   # the "dark" swatch, and nothing else may be this colour

FACINGS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
FRAMES = {"idle": 5, "walk": 9, "run": 9, "jump_rise": 3, "fall": 2, "land": 3,
          "dash": 4, "air_dash": 3, "dive": 3, "attack_1": 5, "attack_2": 5,
          "attack_3": 7, "hurt": 3}

_pal = [(name, srgb8(name)) for name in ORDER + ["dark"]]
_pal_lin = [(name, tuple(srgb_to_linear(c / 255.0) for c in rgb))
            for name, rgb in _pal]


def _hsv(rgb):
    r, g, b = (c / 255.0 for c in rgb)
    mx, mn = max(r, g, b), min(r, g, b)
    v = mx
    s = 0.0 if mx <= 0 else (mx - mn) / mx
    if mx == mn:
        h = 0.0
    elif mx == r:
        h = (60 * (g - b) / (mx - mn)) % 360
    elif mx == g:
        h = 60 * (b - r) / (mx - mn) + 120
    else:
        h = 60 * (r - g) / (mx - mn) + 240
    return h, s, v


_pal_hsv = [(name, _hsv(srgb8(name))) for name in ORDER + ["dark"]]


def nearest(rgb):
    """Which SWATCH a rendered pixel belongs to -- matched on hue and
    saturation, deliberately ignoring brightness.

    Matching on RGB distance does not work here, in either space, and the
    failure is specific: EEVEE's warm key light drags the lit face of the green
    tunic toward yellow, and a straight distance match then lands those pixels
    on the gold swatch. The figure came back with gold speckle sprayed across
    its chest -- twice, once in linear and once with weighted channels.

    Hue does not have that problem. Gold sits near 40 degrees and the greens
    near 100, so a lit green is still unambiguously green however bright the
    key light made it. Brightness is then put back as a shade step in
    `shade_of`, which is what gives the flat 3-tone look the reference sheet
    has anyway.

    Greys and near-greys carry no usable hue, so they are matched on value
    alone against the achromatic swatches.
    """
    h, s, v = _hsv(rgb)
    chromatic = s > 0.18
    best, bd = None, 1e9
    for name, (ph, ps, pv) in _pal_hsv:
        p_chromatic = ps > 0.18
        if chromatic != p_chromatic:
            continue
        if chromatic:
            dh = abs(h - ph)
            dh = min(dh, 360 - dh) / 180.0
            d = dh * dh * 6.0 + (s - ps) ** 2
        else:
            d = (v - pv) ** 2
        if d < bd:
            best, bd = name, d
    if best is None:                       # no swatch of that kind: fall back
        best = min(_pal_hsv, key=lambda kv: (v - kv[1][2]) ** 2)[0]
    return best, v


def shade_of(name, v):
    """The swatch, stepped by how bright the rendered pixel was."""
    base = srgb8(name)
    _, _, pv = dict(_pal_hsv)[name]
    ratio = v / max(pv, 1e-6)
    if ratio < 0.68:
        k = SHADES[0]
    elif ratio < 0.86:
        k = SHADES[1]
    elif ratio <= 1.04:
        k = SHADES[2]
    elif ratio <= 1.18:
        k = SHADES[3]
    else:
        k = SHADES[4]
    return tuple(max(0, min(255, int(round(c * k)))) for c in base)


def quantise(im):
    """Hard alpha, then every opaque pixel snapped to a swatch and a shade."""
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    cache = {}
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a < ALPHA_CUT:
                px[x, y] = (0, 0, 0, 0)
                continue
            key = (r, g, b)
            hit = cache.get(key)
            if hit is None:
                name, v = nearest(key)
                hit = shade_of(name, v)
                cache[key] = hit
            px[x, y] = (hit[0], hit[1], hit[2], 255)
    return im


def outline(im):
    """One dark pixel around the silhouette, 4-connected.

    4-connected rather than 8: an 8-connected outline on a 48 px figure closes
    the 1 px gap between the legs and the character grows a skirt it does not
    have.
    """
    px = im.load()
    w, h = im.size
    edge = []
    for y in range(h):
        for x in range(w):
            if px[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and px[nx, ny][3]:
                    edge.append((x, y))
                    break
    for x, y in edge:
        px[x, y] = (OUTLINE[0], OUTLINE[1], OUTLINE[2], 255)
    return im


def main():
    os.makedirs(OUT, exist_ok=True)
    manifest = {
        "canvas_px": CANVAS_PX,
        "sprite_px": SPRITE_PX,
        "bake_deg": BAKE_DEG,
        "world_h": WORLD_H,
        "facings": FACINGS,
        "palette": {k: SWATCHES[k] for k in ORDER},
        "strips": {},
    }
    missing = []
    stats = defaultdict(int)
    foot_px = CANVAS_PX
    foot_by_facing = {}

    for action, nf in FRAMES.items():
        for fac in FACINGS:
            frames = []
            for f in range(nf):
                src = os.path.join(RAW, "player_%s_%s_%02d.png" % (action, fac, f))
                if not os.path.exists(src):
                    missing.append(os.path.basename(src))
                    continue
                im = outline(quantise(Image.open(src)))
                if im.size != (CANVAS_PX, CANVAS_PX):
                    im = im.resize((CANVAS_PX, CANVAS_PX), Image.NEAREST)
                frames.append(im)
                bb = im.getbbox()
                if bb is None:
                    stats["blank"] += 1
                elif action == "idle":
                    # Anchor on the IDLE pose only. Taking the minimum over every
                    # action anchors on whichever pose reaches lowest -- and then
                    # a jump, whose feet are tucked up, is what defines where the
                    # ground is. The figure floated for exactly that reason.
                    foot_px = min(foot_px, CANVAS_PX - bb[3])
                    foot_by_facing[fac] = min(foot_by_facing.get(fac, CANVAS_PX),
                                              CANVAS_PX - bb[3])
            if not frames:
                continue
            strip = Image.new("RGBA", (CANVAS_PX * len(frames), CANVAS_PX),
                              (0, 0, 0, 0))
            for i, im in enumerate(frames):
                strip.paste(im, (i * CANVAS_PX, 0))
            name = "player_%s_%s.png" % (action, fac)
            strip.save(os.path.join(OUT, name))
            manifest["strips"]["%s_%s" % (action, fac)] = {
                "file": name, "frames": len(frames)}
            stats["strips"] += 1
            stats["frames"] += len(frames)

    # How many empty canvas rows sit UNDER the lowest foot, across every frame.
    # The game subtracts this to put the feet on the ground: the figure is 45 px
    # of a 64 px canvas, so a quad aligned by its own bottom edge hangs the
    # character about a third of a metre in the air, shadow and all.
    manifest["foot_px"] = foot_px
    # ...and per facing. At a steep bake a part's DEPTH becomes screen height,
    # so each facing's boots end on a different row: 103-109 across the eight
    # idle facings at 38 degrees. One shared anchor floated the character up
    # to 6 texels (~0.1 m) in some facings. At 8 degrees the spread is ~2.
    manifest["foot_by_facing"] = foot_by_facing

    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)

    print("PACK " + json.dumps({
        "strips": stats["strips"],
        "frames": stats["frames"],
        "blank_frames": stats["blank"],
        "missing": len(missing),
        "missing_examples": missing[:5],
        "foot_px": foot_px,
        "out": OUT,
    }))


if __name__ == "__main__":
    # --raw=<dir> --out=<dir> --deg=N --only=a,b: pack an alternative bake into
    # its own sprite folder. Defaults are the shipped bake.
    for _a in sys.argv[1:]:
        if _a.startswith("--raw="):
            RAW = _a[6:]
        elif _a.startswith("--out="):
            OUT = os.path.abspath(_a[6:])
        elif _a.startswith("--deg="):
            BAKE_DEG = float(_a[6:])
        elif _a.startswith("--only="):
            FRAMES = {k: v for k, v in FRAMES.items() if k in _a[7:].split(",")}
    main()
