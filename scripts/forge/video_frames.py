# blender -b --factory-startup -P frames.py -- <video> <outdir> <count>
# Renders `count` evenly spaced frames of a video through the sequencer.
import os
import sys

import bpy

argv = sys.argv[sys.argv.index("--") + 1:]
src, out, n = argv[0], argv[1], int(argv[2])
os.makedirs(out, exist_ok=True)

clip = bpy.data.movieclips.load(src)
w, h = clip.size
fps = clip.fps
dur = clip.frame_duration
print(f"VIDEO {os.path.basename(src)} {w}x{h} fps {fps:.2f} frames {dur} seconds {dur / max(fps, 1):.1f}")

sc = bpy.context.scene
sc.sequence_editor_create()
sc.sequence_editor.sequences.new_movie("m", src, 1, 1)
sc.frame_start, sc.frame_end = 1, dur
sc.render.resolution_x, sc.render.resolution_y = w, h
sc.render.resolution_percentage = 100 if w <= 960 else int(960 * 100 / w)
sc.render.use_sequencer = True
sc.render.image_settings.file_format = "JPEG"
sc.render.image_settings.quality = 88
for i in range(n):
    f = 1 + int(i * (dur - 2) / max(n - 1, 1))
    sc.frame_set(f)
    sc.render.filepath = os.path.join(out, f"f{i:02d}_{f / fps:05.1f}s.jpg")
    bpy.ops.render.render(write_still=True)
print("DONE", out)
