"""The player's colours, frozen.

Read off the COLOUR PALETTE column of the reference sheet. Everything the figure
is made of comes from this table and nothing else -- the pixel pass at the end of
the pipeline quantises to exactly these values, so a colour that is not here
cannot survive the bake and will land on whichever swatch is nearest.

sRGB hex in, linear out, because Blender's Base Color input is linear and a hex
value pasted straight in comes out washed.

Values were re-sampled 2026-09-23 from `ref/emberglass_player_sheet.webp`: the
median of a 12x20 px patch per swatch (std <= 1.1 per channel), except the
INFERRED ones noted below, which are arithmetic off a sampled neighbour rather
than a second sample. The previous set was read off the sheet by eye and ran
20-40% too bright.

Nothing here imports bpy: `pack_sheets.py` runs under plain CPython and needs the
same numbers to quantise against.
"""

# name -> sRGB hex, exactly as the sheet's swatch column reads
SWATCHES = {
    "steel":      "#8c8179",   # sampled: sheet swatch column
    "steel_lit":  "#afa197",   # INFERRED: steel x1.25
    "cream":      "#caaf91",   # sampled
    "green_mid":  "#435c43",   # sampled
    "green_sleeve": "#324635",  # INFERRED: midway green_mid..green_deep
    "green_deep": "#223127",   # sampled
    "leather":    "#553829",   # sampled
    "leather_dk": "#3a261c",   # INFERRED: leather x0.68
    "crest":      "#7c3930",   # sampled
    "gold":       "#ac7948",   # sampled
    "skin":       "#ce9f7a",   # sampled: face row median, front view at 35% height
    "dark":       "#17161c",   # unchanged (visor/eyes and outline)
}

# Sheet order, for the contact sheet and for the quantiser's palette file.
ORDER = ["steel", "cream", "green_mid", "green_deep", "green_sleeve",
         "leather", "leather_dk", "crest", "gold", "steel_lit", "skin"]

# Per-swatch roughness. Metal is not smooth here on purpose: a sharp specular
# highlight becomes one blown pixel at 48px and reads as a hole in the armour.
ROUGH = {
    "steel": 0.42, "steel_lit": 0.38, "gold": 0.40,
    "cream": 0.85, "green_mid": 0.80, "green_deep": 0.82, "green_sleeve": 0.80,
    "leather": 0.70, "leather_dk": 0.72, "crest": 0.78, "dark": 0.90,
    "skin": 0.85,
}

# Five shade steps per swatch, indexed 0..4 with 2 == the swatch itself. This is
# the SINGLE definition -- player_paint.py (painting), pack_sheets.py (the
# quantiser) and check_strips.py (the checker) all import this copy rather than
# keeping their own, so a painted texel and a quantised texel always land on the
# same 5-step ramp.
SHADES = (0.58, 0.76, 1.0, 1.14, 1.30)


def srgb_to_linear(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def rgb(name):
    """Linear RGB triple for a swatch name."""
    h = SWATCHES[name].lstrip("#")
    return tuple(srgb_to_linear(int(h[i:i + 2], 16) / 255.0) for i in (0, 2, 4))


def srgb8(name):
    """0-255 sRGB triple -- what the pixel pass quantises against."""
    h = SWATCHES[name].lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def shade8(name, k):
    """0-255 sRGB triple for swatch `name` at shade index k (0..4).

    Exactly `pack_sheets.shade_of`'s arithmetic (base8 * SHADES[k], clamped),
    so a colour painted here is a colour the quantiser can land back on.
    """
    m = SHADES[k]
    return tuple(max(0, min(255, int(round(c * m)))) for c in srgb8(name))


if __name__ == "__main__":
    for k in SWATCHES:
        print(f"{k:14s} {SWATCHES[k]}  linear {tuple(round(v, 4) for v in rgb(k))}")
