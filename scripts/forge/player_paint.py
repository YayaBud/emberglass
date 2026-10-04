"""Hand-painted pixel textures for the player, one face at a time.

A face is painted as a 2D array of SHADE INDICES 0..4 (2 = the swatch itself),
built by a `brush` and optionally an `edges` pass, plus `DECALS` stamped on top.
The final colour of a texel is always `player_palette.shade8(swatch, k)` for
some swatch and some k in 0..4 -- every opaque atlas texel is therefore one of
the palette's 5-step ramp colours by construction, which is the invariant the
self-check below asserts.

numpy only. No bpy: this runs under Blender's python (`player_parts.py`,
`build_player.py`) and under plain CPython (this file's own self-check).
"""
import zlib

import numpy as np

from player_palette import SWATCHES, shade8

# --------------------------------------------------------------------------
# low-level noise: clumps come from a coarse random grid bilinear-upsampled
# and thresholded, not from independent per-texel rolls -- that is what makes
# a "22% base-1" read as a few blotches instead of a salt-and-pepper scatter.
# --------------------------------------------------------------------------


def _clump_mask(h, w, rng, density, cell=3, stretch=1.0):
    """Boolean mask covering ~`density` fraction of texels in soft blobs.

    `stretch` > 1 widens blobs along x (leather's horizontal streaks); the
    same value noise, sampled from a grid with fewer columns than rows.
    """
    if h <= 0 or w <= 0 or density <= 0:
        return np.zeros((h, w), dtype=bool)
    if density >= 1:
        return np.ones((h, w), dtype=bool)
    cy = max(1, cell)
    cx = max(1, int(round(cell * stretch)))
    lh = max(2, h // cy + 2)
    lw = max(2, w // cx + 2)
    grid = rng.random((lh, lw))
    ys = np.linspace(0, lh - 1, h)
    xs = np.linspace(0, lw - 1, w)
    y0 = np.floor(ys).astype(int)
    y1 = np.minimum(y0 + 1, lh - 1)
    x0 = np.floor(xs).astype(int)
    x1 = np.minimum(x0 + 1, lw - 1)
    fy = (ys - y0)[:, None]
    fx = (xs - x0)[None, :]
    top = grid[y0][:, x0] * (1 - fx) + grid[y0][:, x1] * fx
    bot = grid[y1][:, x0] * (1 - fx) + grid[y1][:, x1] * fx
    noise = top * (1 - fy) + bot * fy
    return noise > np.quantile(noise, 1.0 - density)


def _speckle_mask(h, w, rng, density):
    """Independent per-texel rolls -- single specks, not blobs."""
    if h <= 0 or w <= 0 or density <= 0:
        return np.zeros((h, w), dtype=bool)
    return rng.random((h, w)) < density


# --------------------------------------------------------------------------
# brush / edges
# --------------------------------------------------------------------------

_KINDS = ("cloth", "wool", "leather", "steel", "brass", "plume", "skin", "flat")


def brush(kind, w, h, base, seed):
    """Paint one face as shade indices 0..4 around `base`. Deterministic in
    `seed` (derive it with zlib.crc32, never Python's per-process hash())."""
    if kind not in _KINDS:
        raise ValueError("unknown brush kind: %r" % kind)
    rng = np.random.default_rng(seed)
    idx = np.full((h, w), base, dtype=np.int16)

    if kind == "flat":
        pass
    elif kind == "skin":
        idx[_speckle_mask(h, w, rng, 0.03)] -= 1
    elif kind == "cloth":
        idx[_clump_mask(h, w, rng, 0.22, cell=2)] -= 1
        idx[_speckle_mask(h, w, rng, 0.05)] += 1
        idx[_speckle_mask(h, w, rng, 0.02)] -= 2
    elif kind == "wool":
        idx[_clump_mask(h, w, rng, 0.25, cell=3)] -= 1
        idx[_speckle_mask(h, w, rng, 0.08)] += 1
        idx[_speckle_mask(h, w, rng, 0.03)] -= 2
    elif kind == "leather":
        idx[_clump_mask(h, w, rng, 0.20, cell=2, stretch=2.4)] -= 1
        scuff = _speckle_mask(h, w, rng, 0.05)
        if w > 1:
            grow = np.zeros_like(scuff)
            grow[:, 1:] = scuff[:, :-1] & (rng.random((h, w - 1)) < 0.5)
            scuff = scuff | grow
        idx[scuff] += 1
        idx[_speckle_mask(h, w, rng, 0.03)] -= 2
    elif kind == "steel":
        idx[_clump_mask(h, w, rng, 0.15, cell=6)] += 1
        idx[_clump_mask(h, w, rng, 0.10, cell=4)] -= 1
        idx[_speckle_mask(h, w, rng, 0.03)] -= 2
    elif kind == "brass":
        idx[_clump_mask(h, w, rng, 0.15, cell=3)] -= 1
        idx[_speckle_mask(h, w, rng, 0.08)] += 1
    elif kind == "plume":
        # Vertical strands: whole columns alternate base / base-1, then random
        # breaks put some texels back to base so the strands don't read as a
        # perfectly woven stripe.
        cols = rng.random(w) < 0.5
        idx[:, cols] -= 1
        breaks = _speckle_mask(h, w, rng, 0.15)
        idx = np.where(breaks, base, idx)
        idx[_speckle_mask(h, w, rng, 0.05)] += 1

    return np.clip(idx, 0, 4).astype(np.int8)


def edges(idx, kind):
    """Painted edges in place of bevels. Skips faces under 3x3."""
    h, w = idx.shape
    if h < 3 or w < 3:
        return np.clip(idx, 0, 4).astype(np.int8)
    out = idx.astype(np.int16).copy()
    if kind == "side":
        out[0, :] += 1
        out[-1, :] -= 1
        if w >= 5:
            out[:, 0] -= 1
            out[:, -1] -= 1
    elif kind == "top":
        out[0, :] -= 1
        out[-1, :] -= 1
        out[:, 0] -= 1
        out[:, -1] -= 1
    elif kind == "bottom":
        out[:, :] -= 1
    else:
        raise ValueError("unknown edge kind: %r" % kind)
    return np.clip(out, 0, 4).astype(np.int8)


# --------------------------------------------------------------------------
# decals -- legend char -> (swatch, shade), '.' is transparent
# --------------------------------------------------------------------------

DECALS = {
    "tree": ([
        "......G......",
        ".....GGG.....",
        "..G...G...G..",
        "...G..G..G...",
        "....G.G.G....",
        ".G...GGG...G.",
        "..G...G...G..",
        "...G..G..G...",
        "....G.G.G....",
        ".G...GGG...G.",
        "..G...G...G..",
        "...GG.G.GG...",
        ".....GGG.....",
        "......G......",
        "......G......",
        ".....GgG.....",
        "....GGgGG....",
    ], {"G": ("gold", 2), "g": ("gold", 1)}),
    "buckle": ([
        "GGGGG",
        "GdgdG",
        "GdgdG",
        "GGGGG",
    ], {"G": ("gold", 3), "g": ("gold", 1), "d": ("leather_dk", 1)}),
    "boss": ([
        ".GGGG.",
        "GGggGb",
        "GgbbgG",
        "GgbbgG",
        "bGggGb",
        ".bbbb.",
    ], {"G": ("gold", 3), "g": ("gold", 2), "b": ("gold", 1)}),
    "eyes": ([
        "DD......DD",
        "DD......DD",
        "DD......DD",
    ], {"D": ("dark", 2)}),
    "rivet": ([
        "G",
    ], {"G": ("gold", 3)}),
}


def stamp(tile_rgb, decal_name, anchor):
    """Write a decal into `tile_rgb` (uint8 [h,w,3]) in place. Clips to the
    tile; never errors on an anchor that runs the decal off the edge."""
    rows, legend = DECALS[decal_name]
    dh, dw = len(rows), len(rows[0])
    h, w = tile_rgb.shape[:2]
    if anchor == "center":
        col, row = (w - dw) // 2, (h - dh) // 2
    elif anchor == "center-low":
        col, row = (w - dw) // 2, int(round(0.6 * h)) - dh // 2
    else:
        col, row = anchor
    for r, line in enumerate(rows):
        ty = row + r
        if not (0 <= ty < h):
            continue
        for c, ch in enumerate(line):
            if ch == ".":
                continue
            tx = col + c
            if not (0 <= tx < w):
                continue
            swatch, shade = legend[ch]
            tile_rgb[ty, tx] = shade8(swatch, shade)
    return tile_rgb


# --------------------------------------------------------------------------
# Atlas -- online shelf packer
# --------------------------------------------------------------------------


class Atlas:
    """Packs w x h tiles left to right in shelves (rows), each with a 1-texel
    gutter. `size` is the smallest power-of-two square that fits everything.

    ponytail: SHELF_W is a fixed working width rather than a bin-packing
    optimum -- this figure's face count is small enough that it never gets
    close. Revisit with a real bin packer if a future part set overflows it.
    """
    GUTTER = 1
    SHELF_W = 512

    def __init__(self):
        self._cx = 0
        self._cy = 0
        self._shelf_h = 0
        self._max_x = 0
        self._max_y = 0
        self._rects = []       # (x0, y0, x1, y1) incl. gutter -- overlap check
        self.items = {}        # key -> (x, y, w, h), content only

    def add(self, key, w, h):
        g = self.GUTTER
        fw, fh = w + 2 * g, h + 2 * g
        if self._cx > 0 and self._cx + fw > self.SHELF_W:
            self._cy += self._shelf_h
            self._cx = 0
            self._shelf_h = 0
        x0, y0 = self._cx, self._cy
        x, y = x0 + g, y0 + g
        self._rects.append((x0, y0, x0 + fw, y0 + fh))
        self.items[key] = (x, y, w, h)
        self._cx += fw
        self._shelf_h = max(self._shelf_h, fh)
        self._max_x = max(self._max_x, x0 + fw)
        self._max_y = max(self._max_y, y0 + fh)
        return x, y

    @property
    def size(self):
        s = max(self._max_x, self._max_y, 1)
        p = 256
        while p < s:
            p *= 2
        return p

    def compose(self, tiles):
        """tiles: key -> uint8 [h,w,3]. Returns uint8 [S,S,4], row 0 = top."""
        S = self.size
        out = np.zeros((S, S, 4), dtype=np.uint8)
        g = self.GUTTER
        for key, (x, y, w, h) in self.items.items():
            tile = tiles[key]
            out[y:y + h, x:x + w, :3] = tile
            out[y:y + h, x:x + w, 3] = 255
            y0, y1 = max(0, y - g), min(S, y + h + g)
            x0, x1 = max(0, x - g), min(S, x + w + g)
            # edge gutters: replicate the tile's own border texels
            if y - g >= 0:
                out[y - g:y, x:x + w, :3] = tile[0:1, :, :]
                out[y - g:y, x:x + w, 3] = 255
            if y + h < S:
                out[y + h:y1, x:x + w, :3] = tile[-1:, :, :]
                out[y + h:y1, x:x + w, 3] = 255
            if x - g >= 0:
                out[y:y + h, x - g:x, :3] = tile[:, 0:1, :]
                out[y:y + h, x - g:x, 3] = 255
            if x + w < S:
                out[y:y + h, x + w:x1, :3] = tile[:, -1:, :]
                out[y:y + h, x + w:x1, 3] = 255
            # corner gutters: replicate the tile's own corner texel
            corners = ((y - g, y, x - g, x, tile[0, 0]),
                       (y - g, y, x + w, x1, tile[0, -1]),
                       (y + h, y1, x - g, x, tile[-1, 0]),
                       (y + h, y1, x + w, x1, tile[-1, -1]))
            for cy0, cy1, cx0, cx1, colour in corners:
                if cy0 >= 0 and cy1 <= S and cy1 > cy0 and cx0 >= 0 and cx1 <= S and cx1 > cx0:
                    out[cy0:cy1, cx0:cx1, :3] = colour
                    out[cy0:cy1, cx0:cx1, 3] = 255
        return out


# --------------------------------------------------------------------------
# self-check -- plain CPython, no bpy
# --------------------------------------------------------------------------

def _synthetic():
    """~40 faces over every brush kind plus every decal, deterministic."""
    kind_swatch = {"cloth": "green_mid", "wool": "cream", "leather": "leather",
                   "steel": "steel", "brass": "gold", "plume": "crest",
                   "skin": "skin", "flat": "dark"}
    rng = np.random.default_rng(2026)
    atlas = Atlas()
    tiles = {}
    n = 0
    for i in range(32):
        kind = _KINDS[i % len(_KINDS)]
        swatch = kind_swatch[kind]
        w = int(rng.integers(3, 14))
        h = int(rng.integers(3, 14))
        key = "face_%02d_%s" % (i, kind)
        x, y = atlas.add(key, w, h)
        seed = zlib.crc32(key.encode())
        idx = brush(kind, w, h, 2, seed)
        idx = edges(idx, ("side", "top", "bottom")[i % 3])
        lut = np.array([shade8(swatch, k) for k in range(5)], dtype=np.uint8)
        tiles[key] = lut[idx]
        n += 1
    for name in DECALS:
        rows, legend = DECALS[name]
        dh, dw = len(rows), len(rows[0])
        w, h = dw + 4, dh + 4
        key = "decal_" + name
        x, y = atlas.add(key, w, h)
        tile = np.tile(np.array(shade8("dark", 2), dtype=np.uint8), (h, w, 1))
        stamp(tile, name, "center")
        tiles[key] = tile
        n += 1
    return atlas, atlas.compose(tiles), n


if __name__ == "__main__":
    a1, rgba1, n1 = _synthetic()
    a2, rgba2, n2 = _synthetic()
    assert np.array_equal(rgba1, rgba2), "player_paint: not deterministic"

    allowed = {shade8(s, k) for s in SWATCHES for k in range(5)}
    opaque = rgba1[:, :, 3] == 255
    ys, xs = np.where(opaque)
    for y, x in zip(ys.tolist(), xs.tolist()):
        px = tuple(int(c) for c in rgba1[y, x, :3])
        assert px in allowed, "texel (%d,%d) not a palette colour: %s" % (x, y, px)

    rects = a1._rects
    for i in range(len(rects)):
        ax0, ay0, ax1, ay1 = rects[i]
        for j in range(i + 1, len(rects)):
            bx0, by0, bx1, by1 = rects[j]
            if ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1:
                raise AssertionError("reserved rects overlap: %s vs %s" %
                                      (rects[i], rects[j]))

    print("player_paint: PASS (%d faces, atlas %d)" % (n1, a1.size))
