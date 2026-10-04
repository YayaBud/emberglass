"""
Flatten procedural materials to constants so glTF can carry their colour.

THE BUG THIS FIXES. Every material in `detail_materials` drives Principled's
`Base Color` from a noise texture through a ColorRamp. That is what gives the
library its mottled stone and clay, and it renders beautifully in Blender --
but glTF has no procedural node graph. It stores one `baseColorFactor` per
material, and when the Base Color input is LINKED there is no constant to
write, so the exporter falls back to white. The whole city exported colourless:
white houses, white roofs, white ground.

So before export, every material is flattened: the ramp is evaluated at the
noise's most likely value and written back as an unlinked constant. The Blender
side is untouched -- this runs in the export scripts only, after the geometry
is built, on throwaway scenes.

Sampling at three points rather than one because a single midpoint sample of a
two-stop ramp returns the exact blend of both stops, which for a clay roof is
the average of its light and dark tile and reads washed out. Weighting toward
the middle of the noise distribution keeps the material's dominant tone.
"""

import bpy

#: Where to sample the ramp. Noise Fac clusters around 0.5, so these three
#: weighted samples approximate the colour the eye actually reads.
SAMPLES = ((0.38, 0.25), (0.5, 0.5), (0.62, 0.25))


def _find_ramp(node, seen=None):
    """Walk backwards from a node input until a ColorRamp turns up."""
    if seen is None:
        seen = set()
    if node is None or node.name in seen:
        return None
    seen.add(node.name)
    if node.type == 'VALTORGB':
        return node
    for inp in node.inputs:
        for link in inp.links:
            found = _find_ramp(link.from_node, seen)
            if found is not None:
                return found
    return None


def _representative(ramp):
    r = g = b = 0.0
    for pos, weight in SAMPLES:
        c = ramp.color_ramp.evaluate(pos)
        r += c[0] * weight
        g += c[1] * weight
        b += c[2] * weight
    return (r, g, b, 1.0)


def flatten(verbose=False):
    """Give every material a constant base colour glTF can actually store.

    Returns (flattened, already_constant, skipped).
    """
    done = const = skipped = 0
    for mat in bpy.data.materials:
        if not mat.use_nodes or mat.node_tree is None:
            skipped += 1
            continue
        bsdf = None
        for n in mat.node_tree.nodes:
            if n.type == 'BSDF_PRINCIPLED':
                bsdf = n
                break
        if bsdf is None:
            # Emission-only materials export fine: glTF carries an emissive
            # factor, and those are already constants in detail_materials.
            skipped += 1
            continue

        base = bsdf.inputs.get('Base Color')
        if base is None:
            skipped += 1
            continue
        if not base.links:
            const += 1
            continue

        ramp = _find_ramp(base.links[0].from_node)
        if ramp is None:
            skipped += 1
            continue

        colour = _representative(ramp)
        for link in list(base.links):
            mat.node_tree.links.remove(link)
        base.default_value = colour
        # glTF reads roughness and metallic off the same node, and those are
        # already constants here, so nothing else needs touching.
        done += 1
        if verbose:
            print("    %-24s -> (%.3f, %.3f, %.3f)"
                  % (mat.name, colour[0], colour[1], colour[2]))
    return done, const, skipped


if __name__ == "__main__":
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import materials
    import detail_materials

    m = materials.setup_all_materials()
    detail_materials.setup_detail_materials(m)
    d, c, s = flatten(verbose=True)
    print("flattened %d, already constant %d, skipped %d" % (d, c, s))
