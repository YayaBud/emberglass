"""Townsfolk raw frames -> pixel art -> one atlas per person per angle.

    python D:/assests/scripts/forge/folk/pack_folk.py

The player's pixel pass (`pack_sheets.py`), with one change: which swatch a
pixel belongs to comes from the flat Workbench render beside it (`id_*.png`),
not from guessing by hue -- ten palettes of skin, cream, grey and white would
mis-sort. The shade step is the player's (value against the swatch, five
steps), the outline is the player's (4-connected, near-black).

Writes `game/assets/folk/<person>_<deg>.png` -- 8 rows (facings s..se, the
bake's order), 12 columns (idle 0-3, walk 0-7) -- and `manifest.json`, plus a
review sheet at `renders/folk/folk_sheet.png`.
"""
import json
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RAW = os.path.join(HERE, "raw")
OUT = os.path.join(ROOT, "game", "assets", "folk")
SHEET = os.path.join(ROOT, "renders", "folk")
FACINGS = ["s", "sw", "w", "nw", "n", "ne", "e", "se"]
ALPHA_CUT = 128
OUTLINE = (23, 22, 28)
SHADES = (0.58, 0.76, 1.0, 1.14, 1.30)   # player_palette.SHADES


def hexrgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def quantise(arr, ida, sw):
    """Swatch from the flat render (the lit one where the flat one missed an
    edge pixel), shade from the lit value against the swatch's, then the
    outline. Vectorised: 1,920 frames of 128 x 128."""
    op = arr[..., 3] >= ALPHA_CUT
    probe = np.where((ida[..., 3] >= ALPHA_CUT)[..., None], ida[..., :3], arr[..., :3])
    base = sw[(((probe[:, :, None, :] - sw[None, None]) ** 2).sum(-1)).argmin(-1)]
    ratio = arr[..., :3].max(-1) / np.maximum(base.max(-1), 1)
    k = np.select([ratio < 0.68, ratio < 0.86, ratio <= 1.04, ratio <= 1.18], SHADES[:4], SHADES[4])
    res = np.zeros_like(arr)
    res[op, :3] = np.clip(np.round(base * k[..., None]), 0, 255)[op]
    res[op, 3] = 255
    nb = np.zeros_like(op)
    nb[:, 1:] |= op[:, :-1]
    nb[:, :-1] |= op[:, 1:]
    nb[1:, :] |= op[:-1, :]
    nb[:-1, :] |= op[1:, :]
    res[nb & ~op] = OUTLINE + (255,)
    return Image.fromarray(res.astype(np.uint8), "RGBA")


def main():
    pal = json.load(open(os.path.join(HERE, "palette.json")))
    frames = pal["frames"]
    cols = [(a, f) for a, n in frames.items() for f in range(n)]
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(SHEET, exist_ok=True)
    packed, half, top = {}, 0, 128
    # pass 1: quantise everything, and find one cell that holds every frame
    for deg in pal["degs"]:
        d = "%02d" % int(deg)
        for name, swatches in pal["variants"].items():
            sw = np.array([hexrgb(s) for s in swatches], dtype=np.int32)
            for fac in FACINGS:
                for a, f in cols:
                    im = Image.open(os.path.join(RAW, d, name, "%s_%s_%02d.png" % (a, fac, f))).convert("RGBA")
                    ids = Image.open(os.path.join(RAW, d, name, "id_%s_%s_%02d.png" % (a, fac, f))).convert("RGBA")
                    im = quantise(np.asarray(im, dtype=np.int32), np.asarray(ids, dtype=np.int32), sw)
                    bb = im.getbbox()
                    if bb:
                        half = max(half, 64 - bb[0], bb[2] - 64)
                        top = min(top, bb[1])
                    packed[(deg, name, fac, a, f)] = im
    cw, chh = 2 * (half + 1), 128 - max(top - 1, 0)
    y0 = 128 - chh
    manifest = {"tpm": pal["tpm"], "cell_px": [cw, chh], "facings": FACINGS, "degs": pal["degs"],
                "actions": {}, "variants": list(pal["variants"]), "files": {}, "foot_px": {}}
    c = 0
    for a, n in frames.items():
        manifest["actions"][a] = {"col": c, "frames": n}
        c += n
    sheet_rows = []
    for deg in pal["degs"]:
        foot = {}
        for name in pal["variants"]:
            atlas = Image.new("RGBA", (cw * len(cols), chh * len(FACINGS)), (0, 0, 0, 0))
            for row, fac in enumerate(FACINGS):
                for col, (a, f) in enumerate(cols):
                    im = packed[(deg, name, fac, a, f)].crop((64 - cw // 2, y0, 64 + cw // 2, 128))
                    atlas.paste(im, (col * cw, row * chh))
                    if a == "idle" and f == 0 and (bb := im.getbbox()):
                        foot[fac] = min(foot.get(fac, chh), chh - bb[3])
            fn = "%s_%02d.png" % (name, int(deg))
            atlas.save(os.path.join(OUT, fn))
            manifest["files"].setdefault(name, {})[str(int(deg))] = fn
            if deg == pal["degs"][-1]:
                sheet_rows.append(atlas.crop((0, 0, atlas.width, chh * 2)))
        manifest["foot_px"][str(int(deg))] = foot
    with open(os.path.join(OUT, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    sheet = Image.new("RGB", (max(r.width for r in sheet_rows), sum(r.height for r in sheet_rows)), (96, 104, 88))
    y = 0
    for r in sheet_rows:
        sheet.paste(r, (0, y), r)
        y += r.height
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(os.path.join(SHEET, "folk_sheet.png"))
    print("FOLKPACK " + json.dumps({"cell": [cw, chh], "people": len(pal["variants"]), "degs": pal["degs"],
                                    "files": len(pal["variants"]) * len(pal["degs"]), "foot_px": manifest["foot_px"]}))


if __name__ == "__main__":
    main()
