# Editing the world in Godot

Open `game/` in Godot 4.6 .NET, press **Build** once, then open `scenes/world.tscn` (F5 plays it).
Every child is its own scene: select it and use *Open in Editor* to edit it (editing through
"Editable Children" also works, but the scene file is the clean place).

| To change | Edit | How |
|---|---|---|
| a building, prop, tree, rock, lamp, crate | `world/<site>.tscn` | move, rotate, scale, delete; drag new ones in from `prefabs/<kit>/` (every asset: `scenes/asset_sheet.tscn`) |
| people, animals, boat, ship, smoke | `world/<site>.tscn`, `world/city_life.tscn`, `world/village_life.tscn` | walkers are children of their route (a path: drag its points); a stander faces its front |
| roads, trails, walls, rivers, canal, coast, districts, dells, pond, hills, biomes, player start | `world/layout.tscn` | drag path points and markers; a road's width and kind are the node's metadata |
| hills and hollows, ground colour, where grass and trees grow | `world/terrain.tscn` | Terrain3D brushes: sculpt; Color; Paint with the slots Grass / No grass / Woods / No trees / Bare |
| light, fog, sky, exposure, start weather and hour | `world/look/*.tres` | the Inspector |

Pieces dragged in X/Z land on the ground in the game. City pieces keep their height (terraces).

Regenerating a part from code (`--rebake=<site>`, `layout`, `terrain`, `look`, or `all`) replaces your
edits to that part, after copying the old files to `scratch/bake_backup/<date>/`. Plain `--bake` never
overwrites anything you edited.
