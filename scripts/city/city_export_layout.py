"""
Export the city's PLACEMENT LIST to `city_layout.json` for the Godot game.

    python scripts/city/city_export_layout.py

Runs WITHOUT Blender -- placements are plan data, not geometry.

The GLBs say what a townhouse looks like; this says where the 777 of them
stand. `EmberglassCity` reads `buildings` and `props` and draws each kind from
MultiMeshes; `StreetCamera` reads `roads` and slides the camera aim onto the
nearest centreline so a street can be walked down without the rig clipping a
facade.

WHY THIS FILE EXISTS. The layout used to be written by a throwaway script that
lived only in a scratch directory, so re-exporting the city after the radial
rewrite would have shipped new GLBs against the OLD grid placements -- 710
buildings at coordinates that no longer have streets under them. An exporter
the pipeline depends on belongs in the pipeline.

Axes: the layout is in the city's own Blender XY. Both consumers convert.
`EmberglassCity.ToGodot` is (x, y, z) -> (x, z, -y) and `StreetCamera.Load`
does the matching (x, y) -> (x, -y), which is also what the glTF exporter
writes, so placements and terrain share one frame.
"""

import io
import json
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_scripts = os.path.dirname(_here)
for _p in (_scripts, _here):
    if _p not in sys.path:
        sys.path.append(_p)

import city_plan as P
import city_blocks as B
import city_props as PR

OUT = "D:/nanobanna_godot/assets/models/emberglass/city_layout.json"


def _entry(p):
    return {"k": p.kind, "x": round(p.x, 2), "y": round(p.y, 2),
            "z": round(p.z, 2), "yaw": round(p.yaw, 1)}


def main():
    placements, shortfall = B.build_all()
    props = PR.build_all()

    # ALL_ROADS, not MAIN_ROADS. The camera corridor is the thing the player
    # actually walks: the ring roads and the minor spokes are most of the
    # city's street length, and leaving them out left the rig unguided
    # everywhere except five streets.
    roads = [{"n": n, "w": w,
              "pts": [[round(x, 2), round(y, 2)] for (x, y) in pts]}
             for (n, w, pts) in P.ALL_ROADS]

    data = {
        "origin": "emberglass",
        "terraces": P.TERRACE_Z,
        "buildings": [_entry(p) for p in placements],
        "props": [_entry(p) for p in props],
        "roads": roads,
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)

    seg = sum(max(0, len(r["pts"]) - 1) for r in roads)
    print("buildings %d   props %d   roads %d (%d segments)   terraces %d"
          % (len(data["buildings"]), len(data["props"]), len(roads), seg,
             len(P.TERRACE_Z)))
    if shortfall:
        print("SHORTFALL:", shortfall)
    print("->", OUT)


if __name__ == "__main__":
    main()
