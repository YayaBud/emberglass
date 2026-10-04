"""
Render the city plan as the ASCII map that appears in implementation_plan.md.

This exists so the plan and the code cannot drift: the map in the document is
generated from `city_plan`, and `--check` re-renders it and diffs it against
the fenced block in the plan file. If someone moves a district in the data and
forgets the document, this fails.

    python scripts/city/city_map.py            # print the map
    python scripts/city/city_map.py --check    # diff against implementation_plan.md
"""

import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import city_plan as P

W, H = 78, 34
X0, Y0, X1, Y1 = P.TERRAIN

PLAN_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "implementation_plan.md")


def cx(x):
    return max(0, min(W - 1, int(round((x - X0) / (X1 - X0) * (W - 1)))))


def cy(y):
    return max(0, min(H - 1, int(round((Y1 - y) / (Y1 - Y0) * (H - 1)))))


def _blank():
    return [[' '] * W for _ in range(H)]


def _put(g, c, r, ch, over=None):
    if 0 <= r < H and 0 <= c < W:
        if over is None or g[r][c] in over:
            g[r][c] = ch


def _rect(g, x0, y0, x1, y1, ch, over=None):
    for r in range(cy(y1), cy(y0) + 1):
        for c in range(cx(x0), cx(x1) + 1):
            _put(g, c, r, ch, over)


def _seg(g, p0, p1, ch, dash=0, over=None, ph=0):
    c0, r0 = cx(p0[0]), cy(p0[1])
    c1, r1 = cx(p1[0]), cy(p1[1])
    n = max(abs(c1 - c0), abs(r1 - r0))
    for i in range(n + 1):
        t = i / n if n else 0.0
        c = int(round(c0 + (c1 - c0) * t))
        r = int(round(r0 + (r1 - r0) * t))
        if not (dash and ((i + ph) % dash) == dash - 1):
            _put(g, c, r, ch, over)
    return (n + ph + 1) % dash if dash else 0


def _path(g, pts, ch, dash=0, over=None):
    ph = 0
    for a, b in zip(pts, pts[1:]):
        ph = _seg(g, a, b, ch, dash, over, ph)


MARKS = [
    ((60, 180), '+'), ((-200, 40), '+'), ((220, 20), '+'),
    ((150, -120), '+'), ((0, -180), '+'), ((105, 128), '+'),
    ((60, 85), '^'), ((-10, -10), '^'), ((-85, -10), '^'), ((-85, -65), '^'),
    ((-245, 40), 'B'), ((-245, -60), 'B'), ((265, 20), 'B'),
    ((-245, 150), 'V'), ((265, 105), 'V'), ((265, -140), 'V'),
    ((165, 140), 'K'), ((150, 70), 'C'), ((30, 140), 'H'), ((10, 65), 'G'),
    ((0, 40), 'F'), ((290, -60), 'M'), ((-145, -250), 'L'),
    ((-40, -100), 'D'), ((40, -100), 'D'),
]

TOWER_TICKS = [(-200, 85), (-95, 85), (-95, 180), (220, 180), (220, -120),
               (-200, -120), (220, 85), (-200, -10), (60, 180), (220, -10),
               (0, 180), (-95, 130)]


def render():
    g = _blank()

    for d in P.DISTRICTS:
        _rect(g, d.rect[0], d.rect[1], d.rect[2], d.rect[3], d.fill)
    for _, (x0, y0, x1, y1) in P.OPEN_AREAS:
        _rect(g, x0, y0, x1, y1, '.')
    for _, (x0, y0, x1, y1) in P.WATER_RECTS:
        _rect(g, x0, y0, x1, y1, '~')
    _rect(g, *P.LIGHTHOUSE_ISLAND, ch='.')

    for run in P.WALL_RUNS:
        _path(g, run, '#')

    fill_over = ' 123456790."~'
    for _n, _w, pts in P.SECONDARY_ROADS:
        _path(g, pts, '-', dash=3, over=fill_over)
    for _n, _w, pts in P.MAIN_ROADS:
        _path(g, pts, '=', dash=4, over=fill_over + '-')

    for (x, y), ch in MARKS:
        _put(g, cx(x), cy(y), ch)
    for x, y in TOWER_TICKS:
        _put(g, cx(x), cy(y), 'T')

    tick = [' '] * W
    for xm in range(-400, int(X1) + 1, 100):
        lab = "%d" % xm
        c = cx(xm) - len(lab) // 2
        for k, ch in enumerate(lab):
            if 0 <= c + k < W:
                tick[c + k] = ch
    tick2 = [' '] * W
    for xm in range(-400, int(X1) + 1, 100):
        tick2[cx(xm)] = "'"

    out = ["  X->|" + "".join(tick), "     +" + "".join(tick2)]
    for i, row in enumerate(g):
        y = Y1 - i * (Y1 - Y0) / (H - 1)
        out.append("%5d|%s" % (round(y / 10) * 10, "".join(row).rstrip()))
    return "\n".join(out)


def plan_map():
    """The fenced map block currently in implementation_plan.md."""
    s = io.open(PLAN_PATH, encoding="utf-8").read()
    key = "  X->|"
    i = s.index(key)
    j = s.index("```", i)
    return s[i:j].rstrip("\n")


def main():
    got = render()
    if "--check" not in sys.argv:
        print(got)
        return 0
    want = plan_map()
    if got == want:
        print("MAP OK - implementation_plan.md matches city_plan.py")
        return 0
    gl, wl = got.split("\n"), want.split("\n")
    print("MAP MISMATCH: plan document disagrees with city_plan.py")
    for n in range(max(len(gl), len(wl))):
        a = gl[n] if n < len(gl) else "<missing>"
        b = wl[n] if n < len(wl) else "<missing>"
        if a != b:
            print("  line %d\n    code: %s\n    plan: %s" % (n + 1, a, b))
    return 1


if __name__ == "__main__":
    sys.exit(main())
