"""
Smoke-test every generator in detail_primitives.py.

Runs each one in isolation, reports the exception if it throws, and otherwise
reports vert/face/material counts so an empty or degenerate result is obvious
without opening the file. Run headless:

    blender --background --python scripts/test_detail_primitives.py
"""

import bpy
import sys
import os
import traceback

script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.append(script_dir)

import materials
import detail_materials
import detail_primitives as dp


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    mats = materials.setup_all_materials()
    mats = detail_materials.setup_detail_materials(mats)
    print(f"materials: {len(mats)}")

    cases = [
        ("masonry", lambda: dp.create_masonry_box(
            "T_Masonry", 4.4, 5.4, 1.1, mats=mats)),
        ("roof", lambda: dp.create_tiled_roof_y(
            "T_Roof", span_x=4.75, length_y=5.75, mats=mats)[0]),
        ("plaster", lambda: dp.create_plaster_panel(
            "T_Plaster", 2.0, 1.6, mats=mats)),
        ("frame", lambda: dp.create_timber_frame("T_Frame", [
            {"p0": (-1, 0, 0), "p1": (-1, 0, 2.2), "pegs": [0.1, 0.9]},
            {"p0": (1, 0, 0), "p1": (1, 0, 2.2), "pegs": [0.1, 0.9]},
            {"p0": (-1, 0, 2.2), "p1": (1, 0, 2.2), "moss": True},
            {"p0": (-1, 0, 0.2), "p1": (0, 0, 2.0), "w": 0.12},
        ], mats=mats)),
        ("chimney", lambda: dp.create_chimney_detailed("T_Chim", mats=mats)),
        ("ivy", lambda: dp.create_ivy_climber("T_Ivy", 3.0, 1.4, mats=mats)),
        ("ivy_corner", lambda: dp.create_ivy_climber(
            "T_IvyC", 2.6, 1.0, mats=mats, corner=True)),
        ("cobbles", lambda: dp.create_cobble_apron(
            "T_Cobble", 9.0, 9.0, mats=mats, exclude=(-2.4, -3.0, 2.4, 3.0))),
        ("window", lambda: dp.create_window_detailed("T_Win", mats=mats)),
        ("window_shut", lambda: dp.create_window_detailed(
            "T_WinS", mats=mats, shutter_open=False, planter=False)),
        ("door", lambda: dp.create_door_detailed("T_Door", mats=mats)),
        ("bracket", lambda: dp.create_lantern_bracket("T_Brk", mats=mats)),
        ("bracket_bare", lambda: dp.create_lantern_bracket(
            "T_BrkB", mats=mats, lantern=False)),
        ("sign", lambda: dp.create_hanging_sign_detailed("T_Sign", mats=mats)),
        ("barrel", lambda: dp.create_barrel_detailed("T_Barrel", mats=mats)),
        ("barrel_open", lambda: dp.create_barrel_detailed(
            "T_BarrelO", mats=mats, open_top=True, mossy=True)),
        ("crate", lambda: dp.create_crate_detailed("T_Crate", mats=mats)),
        ("bench", lambda: dp.create_bench_detailed("T_Bench", mats=mats)),
        ("firewood", lambda: dp.create_firewood_stack_detailed(
            "T_Wood", mats=mats)),
        ("garden", lambda: dp.create_garden_bed("T_Garden", mats=mats)),
        ("flowerbox", lambda: dp.create_flower_box_standalone_detailed(
            "T_FBox", mats=mats)),
        ("steps", lambda: dp.create_stone_steps_detailed("T_Steps", mats=mats)),
        ("gable", lambda: dp.create_gable_infill(
            "T_Gable", 4.75, 2.64, mats=mats)),
    ]

    failures = []
    for label, fn in cases:
        try:
            obj = fn()
            bpy.context.scene.collection.objects.link(obj)
            # Force the modifier stack to evaluate so a bad bevel shows up here
            dg = bpy.context.evaluated_depsgraph_get()
            ev = obj.evaluated_get(dg)
            m = ev.to_mesh()
            nv, nf = len(m.vertices), len(m.polygons)
            n_slots = max(1, len(obj.data.materials))
            bad = [p.material_index for p in m.polygons
                   if p.material_index >= n_slots]
            ev.to_mesh_clear()
            flag = ""
            if nv == 0 or nf == 0:
                flag = "  <-- EMPTY"
                failures.append(label)
            if bad:
                flag += f"  <-- {len(bad)} OUT-OF-RANGE MAT IDX"
                failures.append(label)
            print(f"  OK   {label:14s} verts={nv:7d} faces={nf:7d} "
                  f"slots={len(obj.data.materials)}{flag}")
        except Exception:
            failures.append(label)
            print(f"  FAIL {label}")
            traceback.print_exc()

    print("")
    if failures:
        print(f"FAILURES ({len(failures)}): {', '.join(sorted(set(failures)))}")
    else:
        print("ALL PRIMITIVES OK")


if __name__ == "__main__":
    main()
