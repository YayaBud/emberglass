"""
Split a built mesh into spatial chunks so the renderer can cull it.

Fixes ledger C17. The structure export used to be three monolithic meshes --
`emberglass_terrain` alone was one 56k-face object spanning 760 x 650 m, so it
could never be frustum-culled: the whole city's ground was drawn whether or not
any of it was on screen.

One pass over the faces, bucketed by centroid. Each bucket becomes its own
object carrying the same material slots, so nothing about the look changes --
only how many draw calls the GPU can skip.
"""

import bpy
import bmesh
from collections import defaultdict


def chunk_key(x, y, size):
    return (int(x // size), int(y // size))


def split_by_chunk(obj, size, prefix):
    """Split `obj` into one object per occupied chunk.

    Returns {(cx, cy): object}. The source object is left alone; the caller
    decides whether to keep or delete it.
    """
    mesh = obj.data
    mats = list(mesh.materials)
    mw = obj.matrix_world

    bm = bmesh.new()
    bm.from_mesh(mesh)
    bm.faces.ensure_lookup_table()

    buckets = defaultdict(list)
    for f in bm.faces:
        c = mw @ f.calc_center_median()
        buckets[chunk_key(c.x, c.y, size)].append(f)

    out = {}
    for key, faces in buckets.items():
        # Remap only the vertices this chunk actually uses.
        vmap = {}
        verts = []
        polys = []
        midx = []
        for f in faces:
            idx = []
            for v in f.verts:
                if v.index not in vmap:
                    vmap[v.index] = len(verts)
                    verts.append((mw @ v.co)[:])
                idx.append(vmap[v.index])
            polys.append(idx)
            midx.append(f.material_index)

        nm = bpy.data.meshes.new("%s_%d_%d" % (prefix, key[0], key[1]))
        nm.from_pydata(verts, [], polys)
        nm.update()
        for m in mats:
            nm.materials.append(m)
        for i, p in enumerate(nm.polygons):
            p.material_index = midx[i]

        nob = bpy.data.objects.new(nm.name, nm)
        bpy.context.scene.collection.objects.link(nob)
        out[key] = nob

    bm.free()
    return out


def split_many(objs, size, prefix):
    """Split several objects and merge them per chunk.

    Terrain, walls and roads all land in the same chunk bucket, so one chunk
    GLB carries every system in that square rather than three.
    """
    merged = defaultdict(list)
    for o in objs:
        if o.type != 'MESH' or not o.data.polygons:
            continue
        for key, nob in split_by_chunk(o, size, prefix).items():
            merged[key].append(nob)
    return merged
