"""Texel density of every exported kit GLB, triangle by triangle.

    python D:/assests/scripts/forge/kit/density.py

Reads the GLBs back (not the Blender scene), so it checks what the game will
load: for each triangle, sqrt(UV area x texture px area / world area) is the
texels per metre it is drawn at. Target 52 +-15% (hd2d audit Law 2). Glow and
flat materials have no texture and are skipped.
"""
import glob
import json
import os
import struct
import sys

import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
KIT = os.path.join(ROOT, "game", "assets", "models", "kit")
TEX = json.load(open(os.path.join(ROOT, "game", "assets", "tex", "manifest.json")))
TPM, PX = TEX["texels_per_m"], {k: v["px"] for k, v in TEX["surfaces"].items()}
CT = {5126: np.float32, 5125: np.uint32, 5123: np.uint16, 5121: np.uint8}
NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}


def read(j, binary, i):
    a = j["accessors"][i]
    bv = j["bufferViews"][a["bufferView"]]
    off = bv.get("byteOffset", 0) + a.get("byteOffset", 0)
    n = NC[a["type"]]
    arr = np.frombuffer(binary, dtype=CT[a["componentType"]], count=a["count"] * n, offset=off)
    return arr.reshape(a["count"], n) if n > 1 else arr


def main():
    fails = 0
    for path in sorted(glob.glob(os.path.join(KIT, "*.glb"))):
        b = open(path, "rb").read()
        jl = struct.unpack_from("<I", b, 12)[0]
        j = json.loads(b[20:20 + jl])
        binary = b[20 + jl + 8:]
        per = {}
        for node in j["nodes"]:
            if "mesh" not in node or node["name"].startswith(("SHADOW_", "COL_")):
                continue
            for pr in j["meshes"][node["mesh"]]["primitives"]:
                mat = j["materials"][pr["material"]]["name"] if "material" in pr else None
                if mat not in PX or "TEXCOORD_0" not in pr["attributes"]:
                    continue
                P = read(j, binary, pr["attributes"]["POSITION"]).astype(np.float64)
                U = read(j, binary, pr["attributes"]["TEXCOORD_0"]).astype(np.float64)
                I = read(j, binary, pr["indices"]).reshape(-1, 3)
                a, bb, c = P[I[:, 0]], P[I[:, 1]], P[I[:, 2]]
                area = np.linalg.norm(np.cross(bb - a, c - a), axis=1) / 2
                ua, ub, uc = U[I[:, 0]], U[I[:, 1]], U[I[:, 2]]
                e1, e2 = ub - ua, uc - ua
                uva = np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0]) / 2
                ok = area > 1e-4
                pw, ph = PX[mat]
                d = np.sqrt(uva[ok] * pw * ph / area[ok])
                per.setdefault(mat, []).append(d)
        print(os.path.basename(path))
        for mat, ds in sorted(per.items()):
            d = np.concatenate(ds)
            bad = np.mean((d < TPM * 0.85) | (d > TPM * 1.15))
            fails += bad > 0
            print(f"  {mat:<11} tris {len(d):>5}  texels/m min {d.min():6.1f}  median {np.median(d):6.1f}  "
                  f"max {d.max():6.1f}  outside +-15%: {bad * 100:5.1f}%")
    print("density:", "PASS" if fails == 0 else f"FAIL ({fails} materials with triangles off target)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
