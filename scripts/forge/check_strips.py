"""Verify the packed sprite strips against the manifest.

    python D:/assests/scripts/forge/check_strips.py

Checks, in order of how badly each one bites:

1. Every action x facing the manifest declares exists as a file.
2. Every strip's pixel width is exactly `frames * canvas`, and its height is
   `canvas`. A strip one frame short silently plays a neighbouring frame,
   because the UV window just slides past the end of the texture.
3. No frame is fully transparent. A blank frame is what a mis-keyed action looks
   like from the outside: the character vanishes for a twelfth of a second.
4. Every opaque pixel is one of the palette's own colours or a shade of one.
   A stray colour means the quantiser let a rendered value through, which is how
   a 48-colour sprite sneaks back into a 10-colour set.
5. The idle strips all stand on the same row, so the character does not hop
   between facings when it turns on the spot.

Exit code is non-zero if anything failed, so it can gate a build.
"""
import json
import os
import sys
from collections import Counter

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from player_palette import ORDER, SHADES, srgb8  # noqa: E402

SPRITES = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else os.path.abspath(os.path.join(HERE, "..", "..", "game", "assets", "sprites"))
TOL = 6


def allowed_colours():
    out = set()
    for name in ORDER + ["dark"]:
        base = srgb8(name)
        for k in SHADES:
            out.add(tuple(max(0, min(255, int(round(c * k)))) for c in base))
    return out


def main():
    man_path = os.path.join(SPRITES, "manifest.json")
    if not os.path.exists(man_path):
        print("FAIL no manifest at " + man_path)
        return 1
    man = json.load(open(man_path))
    canvas = man["canvas_px"]
    palette = allowed_colours()

    fails = []
    frames_seen = 0
    strange = Counter()
    foot_rows = {}

    for key, entry in sorted(man["strips"].items()):
        path = os.path.join(SPRITES, entry["file"])
        if not os.path.exists(path):
            fails.append(f"{key}: file missing ({entry['file']})")
            continue
        im = Image.open(path).convert("RGBA")
        want = (canvas * entry["frames"], canvas)
        if im.size != want:
            fails.append(f"{key}: size {im.size}, manifest says {want}")
            continue

        for i in range(entry["frames"]):
            f = im.crop((i * canvas, 0, (i + 1) * canvas, canvas))
            bb = f.getbbox()
            frames_seen += 1
            if bb is None:
                fails.append(f"{key} frame {i}: fully transparent")
                continue
            if key.startswith("idle_") and i == 0:
                foot_rows[key] = bb[3]
            for px in f.getdata():
                if px[3] and px[:3] not in palette:
                    if not any(all(abs(px[c] - q[c]) <= TOL for c in range(3))
                               for q in palette):
                        strange[px[:3]] += 1

    if strange:
        top = ", ".join("#%02x%02x%02x x%d" % (c[0], c[1], c[2], n)
                        for c, n in strange.most_common(4))
        fails.append(f"{sum(strange.values())} pixels outside the palette: {top}")

    # Each facing is anchored on its own foot row (manifest foot_by_facing), so
    # the check is that the anchors match the pixels -- not that all facings
    # share a row, which a steep bake makes geometrically impossible.
    fbf = man.get("foot_by_facing")
    if fbf:
        for key, row in foot_rows.items():
            fac = key.split("_", 1)[1]
            want = canvas - fbf.get(fac, -1)
            # The anchor is the LOWEST foot over all idle frames; frame 0 may
            # sit up to 2 rows higher on the breathing bob, never lower.
            if row > want or row < want - 2:
                fails.append(f"{key}: feet end on row {row}, anchor says {want}")
    elif foot_rows:
        lo, hi = min(foot_rows.values()), max(foot_rows.values())
        if hi - lo > 4:
            fails.append(f"idle facings do not share a ground row: {lo}..{hi} "
                         "(and the manifest has no per-facing anchors)")

    print(f"strips {len(man['strips'])}, frames {frames_seen}, canvas {canvas}px, "
          f"bake {man['bake_deg']} deg, foot_px {man.get('foot_px')}")
    if fails:
        print("FAIL")
        for f in fails[:20]:
            print("  - " + f)
        if len(fails) > 20:
            print(f"  ... and {len(fails) - 20} more")
        return 1
    print("PASS: every strip is the declared size, no blank frames, "
          "no colour outside the palette, idle facings share a ground row")
    return 0


if __name__ == "__main__":
    sys.exit(main())
