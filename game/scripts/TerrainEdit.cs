using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;
using Godot;

namespace Worldbuilder;

/// <summary>
/// Terrain3D as the editor's sculpt and paint tool (implementation_plan Phases 4-5, as built):
/// `res://world/terrain.tscn` is a Terrain3D node over the map and Emberglass (2 m vertices,
/// 512 m regions, data in `res://world/terrain3d/`), showing the game's own ground colours
/// (its colour map, `show_colormap`). The game does not draw it -- the ground stays
/// <see cref="Terrain"/>'s -- it reads what was edited, against what was baked:
/// - Sculpt (height brushes): Terrain3D's height minus the baked height
///   (`terrain_ref_height.res`), added to <see cref="WorldGen.Height"/> (<see cref="Offset"/>).
/// - Colour (colour brush): a colour-map texel that differs from the baked colour
///   (`terrain_ref_color.res`) replaces the generated ground colour (<see cref="Paint"/>).
/// - Zones (texture brush, the slots named in <see cref="Zones"/>): grass and the map-wide
///   trees read the painted slot (<see cref="GrassZone"/>, <see cref="ScatterZone"/>).
/// Nothing edited = every offset 0, no colour, zone 0 = the world as generated; the layout's
/// carving (canal, rivers, dells, terraces) still happens underneath.
/// ponytail: only the baked area (<see cref="Area"/>) is read; regions added outside it are
/// ignored. `--rebake=terrain` re-bakes the display from the current ground, keeping edits.
/// </summary>
public static class TerrainEdit
{
    public const string Scene = "res://world/terrain.tscn";
    public const string DataDir = "res://world/terrain3d";
    public const string RefHeight = "res://world/terrain_ref_height.res";
    public const string RefColor = "res://world/terrain_ref_color.res";
    /// <summary>The ground's vertex spacing (<see cref="Terrain.Cell"/>): one Terrain3D vertex per game vertex.</summary>
    public const float Step = 2f;
    public const int RegionPx = 256;
    /// <summary>The map (+-512 m) and Emberglass (centre (0, -1050), 400 m), on the 512 m region grid.</summary>
    public static readonly Rect2 Area = new(-512f, -1536f, 1024f, 2048f);
    private static int W => (int)(Area.Size.X / Step);
    private static int H => (int)(Area.Size.Y / Step);

    /// <summary>The texture brush's slots and what each means to the game (0 = as generated).</summary>
    public static readonly (string Name, Color Swatch)[] Zones =
    {
        ("As generated", new Color(0.45f, 0.45f, 0.45f)), ("Grass", new Color(0.25f, 0.6f, 0.2f)),
        ("No grass", new Color(0.6f, 0.45f, 0.25f)), ("Woods", new Color(0.1f, 0.35f, 0.12f)),
        ("No trees", new Color(0.8f, 0.75f, 0.4f)), ("Bare", new Color(0.55f, 0.5f, 0.45f)),
    };
    public const int ZGrass = 1, ZNoGrass = 2, ZWoods = 3, ZNoTrees = 4, ZBare = 5;

    private static float[]? _dh;
    private static byte[]? _paint;   // RGBA per vertex, A = 255 where painted
    private static byte[]? _zone;

    private static bool Cell(float x, float z, out int ix, out int iz, out float tx, out float tz)
    {
        var fx = (x - Area.Position.X) / Step;
        var fz = (z - Area.Position.Y) / Step;
        ix = Mathf.FloorToInt(fx);
        iz = Mathf.FloorToInt(fz);
        tx = fx - ix;
        tz = fz - iz;
        return ix >= 0 && iz >= 0 && ix < W - 1 && iz < H - 1;
    }

    /// <summary>What was sculpted at (x, z), in metres (bilinear between vertices; 0 outside the area or when nothing is).</summary>
    public static float Offset(float x, float z)
    {
        var g = _dh;
        if (g == null || !Cell(x, z, out var ix, out var iz, out var tx, out var tz)) return 0f;
        var i = iz * W + ix;
        return Mathf.Lerp(Mathf.Lerp(g[i], g[i + 1], tx), Mathf.Lerp(g[i + W], g[i + W + 1], tx), tz);
    }

    /// <summary>The generated ground colour, or the painted one where the colour brush went
    /// (bilinear over the painted vertices, so a painted edge blends over 2 m).</summary>
    public static Color Paint(float x, float z, Color generated)
    {
        var g = _paint;
        if (g == null || !Cell(x, z, out var ix, out var iz, out var tx, out var tz)) return generated;
        float r = 0f, gr = 0f, b = 0f, wsum = 0f;
        void Add(int i, float w)
        {
            if (g[i * 4 + 3] == 0 || w <= 0f) return;
            r += g[i * 4] * w; gr += g[i * 4 + 1] * w; b += g[i * 4 + 2] * w; wsum += w;
        }
        var k = iz * W + ix;
        Add(k, (1 - tx) * (1 - tz)); Add(k + 1, tx * (1 - tz)); Add(k + W, (1 - tx) * tz); Add(k + W + 1, tx * tz);
        if (wsum <= 0f) return generated;
        var painted = new Color(r / wsum / 255f, gr / wsum / 255f, b / wsum / 255f, generated.A);
        return generated.Lerp(painted, wsum);
    }

    /// <summary>The texture brush's slot at the nearest vertex (0 = as generated).</summary>
    public static int Zone(float x, float z)
    {
        var g = _zone;
        if (g == null || !Cell(x + Step / 2f, z + Step / 2f, out var ix, out var iz, out _, out _)) return 0;
        return g[iz * W + ix];
    }

    /// <summary>Grass density under the painted zone: Grass fills in, No grass / Bare clear it.</summary>
    public static float GrassZone(float x, float z, float d) => Zone(x, z) switch
    {
        ZGrass => Mathf.Max(d, 0.9f),
        ZNoGrass or ZBare => 0f,
        _ => d,
    };

    /// <summary>The map-wide scatter's density (layer 0 trees, 1 undergrowth) under the painted
    /// zone: Woods thickens both, No trees clears the trees, Bare clears both.</summary>
    public static float ScatterZone(float x, float z, int layer, float d) => Zone(x, z) switch
    {
        ZWoods => Mathf.Max(d, layer == 0 ? 0.6f : 0.3f),
        ZNoTrees => layer == 0 ? 0f : d,
        ZBare => 0f,
        _ => d,
    };

    // ------------------------------------------------------------------ load

    private readonly record struct Region(Vector2I Loc, Image Height, Image? Color, Image? Control);

    /// <summary>Terrain3D's saved regions and their maps.</summary>
    private static List<Region> Regions()
    {
        var list = new List<Region>();
        if (!DirAccess.DirExistsAbsolute(ProjectSettings.GlobalizePath(DataDir))) return list;
        foreach (var f in DirAccess.GetFilesAt(DataDir).Where(f => f.EndsWith(".res")))
        {
            var r = ResourceLoader.Load($"{DataDir}/{f}", "", ResourceLoader.CacheMode.Ignore);
            if (r == null || r.Get("height_map").AsGodotObject() is not Image h) continue;
            // where it is comes from the file name (terrain3d-01_00 = (-1, 0)): a region loaded on
            // its own does not carry its location (read as the property, 7 of 8 landed elsewhere)
            var n = f.GetBaseName()["terrain3d".Length..];
            int Part(int at) => (n[at] == '-' ? -1 : 1) * int.Parse(n.Substring(at + 1, 2));
            list.Add(new Region(new Vector2I(Part(0), Part(3)), h,
                r.Get("color_map").AsGodotObject() as Image, r.Get("control_map").AsGodotObject() as Image));
        }
        return list;
    }

    private static float[] Floats(Image img)
    {
        if (img.GetFormat() != Image.Format.Rf) img.Convert(Image.Format.Rf);
        return MemoryMarshal.Cast<byte, float>(img.GetData()).ToArray();
    }

    private static byte[] Rgba(Image img)
    {
        if (img.GetFormat() != Image.Format.Rgba8) img.Convert(Image.Format.Rgba8);
        return img.GetData();
    }

    /// <summary>Calls `each(grid index, region pixel index)` for every region pixel inside the area.</summary>
    private static void Over(Region r, int rw, int rh, System.Action<int, int> each)
    {
        var px = r.Loc.X * RegionPx - (int)(Area.Position.X / Step);
        var pz = r.Loc.Y * RegionPx - (int)(Area.Position.Y / Step);
        for (var j = 0; j < rh; j++)
        for (var i = 0; i < rw; i++)
        {
            int gx = px + i, gz = pz + j;
            if (gx >= 0 && gz >= 0 && gx < W && gz < H) each(gz * W + gx, j * rw + i);
        }
    }

    /// <summary>Sculpted = region height - baked height, per vertex; null when nothing differs by 0.1 mm.</summary>
    private static float[]? Sculpted(float[] baked, List<Region> regions, out float max, out int count)
    {
        var d = new float[W * H];
        float mx = 0f;
        var n = 0;
        foreach (var r in regions)
        {
            var hm = Floats(r.Height);
            Over(r, r.Height.GetWidth(), r.Height.GetHeight(), (g, p) =>
            {
                var v = hm[p] - baked[g];
                d[g] = v;
                if (Mathf.Abs(v) > mx) mx = Mathf.Abs(v);
                if (Mathf.Abs(v) > 1e-4f) n++;
            });
        }
        (max, count) = (mx, n);
        return n == 0 ? null : d;
    }

    /// <summary>Painted = a colour-map texel off the baked colour by more than 2/255.</summary>
    private static byte[]? Painted(byte[] baked, List<Region> regions, out int count)
    {
        var d = new byte[W * H * 4];
        var n = 0;
        foreach (var r in regions.Where(r => r.Color != null))
        {
            var cm = Rgba(r.Color!);
            Over(r, r.Color!.GetWidth(), r.Color.GetHeight(), (g, p) =>
            {
                var off = 0;
                for (var c = 0; c < 3; c++) off = Mathf.Max(off, Mathf.Abs(cm[p * 4 + c] - baked[g * 4 + c]));
                if (off <= 2) return;
                for (var c = 0; c < 3; c++) d[g * 4 + c] = cm[p * 4 + c];
                d[g * 4 + 3] = 255;
                n++;
            });
        }
        count = n;
        return n == 0 ? null : d;
    }

    /// <summary>The texture brush's slot per vertex: the base texture, or the overlay where it
    /// is blended over half (control map bits: base 27-31, overlay 22-26, blend 14-21).</summary>
    private static byte[]? Zoned(List<Region> regions, out int count)
    {
        var d = new byte[W * H];
        var n = 0;
        foreach (var r in regions.Where(r => r.Control != null))
        {
            var ctl = r.Control!;
            if (ctl.GetFormat() != Image.Format.Rf) continue;
            var bits = MemoryMarshal.Cast<byte, uint>(ctl.GetData()).ToArray();
            Over(r, ctl.GetWidth(), ctl.GetHeight(), (g, p) =>
            {
                var v = bits[p];
                var z = (v >> 14 & 0xFF) >= 128 ? v >> 22 & 0x1F : v >> 27 & 0x1F;
                if (z == 0 || z >= Zones.Length) return;
                d[g] = (byte)z;
                n++;
            });
        }
        count = n;
        return n == 0 ? null : d;
    }

    /// <summary>Called by <see cref="Layout.Boot"/>, after the layout: what was sculpted, painted and zoned.</summary>
    public static void Load()
    {
        if (!ResourceLoader.Exists(RefHeight)) return;
        var t0 = Time.GetTicksMsec();
        var regions = Regions();
        if (regions.Count == 0) { GD.PushWarning("terrain: no Terrain3D regions (is the extension loaded?)"); return; }
        _dh = Sculpted(Floats(ResourceLoader.Load<Image>(RefHeight, "", ResourceLoader.CacheMode.Ignore)), regions, out var max, out var n);
        var painted = 0;
        if (ResourceLoader.Exists(RefColor))
            _paint = Painted(Rgba(ResourceLoader.Load<Image>(RefColor, "", ResourceLoader.CacheMode.Ignore)), regions, out painted);
        _zone = Zoned(regions, out var zoned);
        GD.Print($"terrain: {regions.Count} Terrain3D regions: {n} vertices sculpted (max {max:F2} m), {painted} painted, {zoned} zoned, {Time.GetTicksMsec() - t0} ms");
    }

    // ------------------------------------------------------------------ bake

    private static ImageTexture Swatch(Color c)
    {
        var img = Image.CreateEmpty(64, 64, false, Image.Format.Rgba8);
        img.Fill(c);
        img.GenerateMipmaps();
        return ImageTexture.CreateFromImage(img);
    }

    /// <summary>--bake (if there is no terrain yet) or --rebake=terrain: the ground as it is now
    /// (edits included) into Terrain3D, and the generated ground (edits excluded) as the
    /// reference, so what was sculpted and painted survives a re-bake.</summary>
    public static void Bake(Node3D parent)
    {
        var rebake = Worldbuilder.Bake.Rebake.Contains("terrain") || Worldbuilder.Bake.Rebake.Contains("all");
        if (ResourceLoader.Exists(Scene) && !rebake) return;
        var t0 = Time.GetTicksMsec();
        int w = W, h = H;
        var hs = new float[w * h];
        var gen = new float[w * h];
        var cs = new byte[w * h * 4];
        var gc = new byte[w * h * 4];
        static void Put(byte[] to, int k, Color c, byte a)
        {
            to[k * 4] = (byte)(Mathf.Clamp(c.R, 0f, 1f) * 255f + 0.5f);
            to[k * 4 + 1] = (byte)(Mathf.Clamp(c.G, 0f, 1f) * 255f + 0.5f);
            to[k * 4 + 2] = (byte)(Mathf.Clamp(c.B, 0f, 1f) * 255f + 0.5f);
            to[k * 4 + 3] = a;
        }
        Parallel.For(0, h, j =>
        {
            for (var i = 0; i < w; i++)
            {
                float x = Area.Position.X + i * Step, z = Area.Position.Y + j * Step;
                var k = j * w + i;
                hs[k] = WorldGen.Height(x, z);
                gen[k] = hs[k] - Offset(x, z);
                var slope = WorldGen.Slope(x, z);
                var g = WorldGen.AlbedoGen(x, z, slope, out _, out _);
                Put(gc, k, g, 255);
                Put(cs, k, Paint(x, z, g), 128);   // Terrain3D's colour-map alpha is roughness; 0.5 = unchanged
            }
        });
        var hImg = Image.CreateFromData(w, h, false, Image.Format.Rf, MemoryMarshal.AsBytes<float>(hs).ToArray());
        var cImg = Image.CreateFromData(w, h, false, Image.Format.Rgba8, cs);
        var sampled = Time.GetTicksMsec() - t0;

        if (ResourceLoader.Exists(Scene)) Backup();
        var dir = ProjectSettings.GlobalizePath(DataDir);
        DirAccess.MakeDirRecursiveAbsolute(dir);
        var keepZones = Regions();   // the painted zones live in the control maps: carried over below
        foreach (var f in DirAccess.GetFilesAt(DataDir).Where(f => f.EndsWith(".res"))) DirAccess.RemoveAbsolute(dir.PathJoin(f));   // the last bake's regions (backed up above)

        var t = ClassDB.Instantiate("Terrain3D").As<Node3D>();
        t.Name = "Terrain3D";
        t.Set("vertex_spacing", Step);
        t.Set("region_size", RegionPx);
        t.Set("collision_mode", 4);    // FULL_EDITOR: colliders in the editor (Snap to Floor), none in the game
        parent.AddChild(t);
        var mat = t.Get("material").AsGodotObject();
        mat.Set("world_background", 0);   // NONE: no endless plane round the regions
        mat.Set("show_colormap", true);   // the game's ground colours, not the zone swatches (bake 4: it was on the node, did nothing)
        // the zone slots, saved as files (Terrain3D warns on textures and assets that are not)
        const string zones = "res://world/terrain_zones";
        DirAccess.MakeDirRecursiveAbsolute(ProjectSettings.GlobalizePath(zones));
        Texture2D Saved(Color c, string name)
        {
            var tex = Swatch(c);
            ResourceSaver.Save(tex, $"{zones}/{name}.res");
            tex.TakeOverPath($"{zones}/{name}.res");
            return tex;
        }
        var assets = ClassDB.Instantiate("Terrain3DAssets").As<Resource>();
        for (var i = 0; i < Zones.Length; i++)
        {
            var ta = ClassDB.Instantiate("Terrain3DTextureAsset").AsGodotObject();
            ta.Set("name", Zones[i].Name);
            ta.Set("albedo_texture", Saved(Zones[i].Swatch, $"zone_{i}_albedo"));
            ta.Set("normal_texture", Saved(new Color(0.5f, 0.5f, 1f, 0.8f), $"zone_{i}_normal"));
            assets.Call("set_texture", i, ta);
        }
        ResourceSaver.Save(assets, $"{zones}/assets.tres");
        assets.TakeOverPath($"{zones}/assets.tres");
        t.Set("assets", assets);
        var data = t.Get("data").AsGodotObject();
        data.Call("import_images", new Godot.Collections.Array<Image> { hImg, null!, cImg }, new Vector3(Area.Position.X, 0f, Area.Position.Y), 0f, 1f);
        foreach (var r in keepZones.Where(r => r.Control != null))
            data.Call("get_region", r.Loc).AsGodotObject()?.Set("control_map", r.Control);
        data.Call("save_directory", DataDir);
        ResourceSaver.Save(Image.CreateFromData(w, h, false, Image.Format.Rf, MemoryMarshal.AsBytes<float>(gen).ToArray()), RefHeight);
        ResourceSaver.Save(Image.CreateFromData(w, h, false, Image.Format.Rgba8, gc), RefColor);

        // the vertices must line up with the game's: Terrain3D's height at every 64th vertex
        var err = 0f;
        for (var j = 0; j < h; j += 64)
        for (var i = 0; i < w; i += 64)
        {
            var p = new Vector3(Area.Position.X + i * Step, 0f, Area.Position.Y + j * Step);
            err = Mathf.Max(err, Mathf.Abs(data.Call("get_height", p).AsSingle() - hs[j * w + i]));
        }

        t.Set("data_directory", DataDir);
        var ps = new PackedScene();
        var e = ps.Pack(t);
        if (e == Error.Ok) e = ResourceSaver.Save(ps, Scene);
        parent.RemoveChild(t);
        t.QueueFree();
        var regions = Regions();
        GD.Print($"terrain: baked {w}x{h} vertices ({Step} m) in {sampled} ms, {regions.Count} regions to {DataDir}, scene {Scene}: {e}; "
                 + $"Terrain3D height vs the game's at {(w / 64) * (h / 64)} vertices: max err {err:G3} m -> {(err < 1e-3f && regions.Count > 0 ? "PASS" : "FAIL")}");
        Check(gen, gc, regions);
    }

    /// <summary>After a bake: the saved regions read back must carry exactly the edits the bake
    /// kept; then a 5 m bump, a red daub and two zones pressed into region (0, 0), as the
    /// editor's brushes would, must reach the game's height, colour, grass and trees there
    /// and nowhere else; then the saved regions are read again.</summary>
    private static void Check(float[] gen, byte[] gc, List<Region> regions)
    {
        var h0 = WorldGen.Height(0f, 0f);
        var c0 = WorldGen.Albedo(0f, 0f, 0f);
        _dh = Sculpted(gen, regions, out var max, out var n);
        _paint = Painted(gc, regions, out var np);
        _zone = Zoned(regions, out var nz);
        GD.Print($"terrain check: read back {regions.Count} regions: {n} vertices sculpted (max {max:G3} m), {np} painted, {nz} zoned -> {(n == 0 && np == 0 ? "PASS" : "FAIL")}");
        if (!regions.Any(r => r.Loc == Vector2I.Zero)) { GD.PrintErr("terrain check: no region (0, 0) -> FAIL"); return; }
        var r0 = regions.First(r => r.Loc == Vector2I.Zero);
        var bumped = (Image)r0.Height.Duplicate();
        var red = r0.Color != null ? (Image)r0.Color.Duplicate() : null;
        var ctl = r0.Control != null ? (Image)r0.Control.Duplicate() : null;
        for (var j = 0; j < 4; j++)
        for (var i = 0; i < 4; i++)
        {
            bumped.SetPixel(i, j, new Color(bumped.GetPixel(i, j).R + 5f, 0f, 0f));
            red?.SetPixel(i, j, new Color(1f, 0f, 0f, 0.5f));
        }
        if (ctl != null)
        {
            if (ctl.GetFormat() != Image.Format.Rf) ctl.Convert(Image.Format.Rf);
            var bits = MemoryMarshal.Cast<byte, uint>(ctl.GetData()).ToArray();
            // No grass under the bump; No trees 20 m along
            for (var j = 0; j < 4; j++)
            for (var i = 0; i < 4; i++)
            {
                bits[j * ctl.GetWidth() + i] = (uint)ZNoGrass << 27;
                bits[j * ctl.GetWidth() + i + 10] = (uint)ZNoTrees << 27;
            }
            ctl = Image.CreateFromData(ctl.GetWidth(), ctl.GetHeight(), false, Image.Format.Rf, MemoryMarshal.AsBytes<uint>(bits).ToArray());
        }
        var edited = regions.Select(r => r.Loc == Vector2I.Zero ? r with { Height = bumped, Color = red, Control = ctl } : r).ToList();
        _dh = Sculpted(gen, edited, out _, out n);
        _paint = Painted(gc, edited, out np);
        _zone = Zoned(edited, out nz);
        var lifted = WorldGen.Height(0f, 0f) - h0;
        var col = WorldGen.Albedo(0f, 0f, 0f);
        var ok = n == 16 && Mathf.Abs(lifted - 5f) < 1e-3f && Offset(40f, 40f) == 0f
                 && np == 16 && col.R > 0.99f && col.G < 0.01f && Mathf.IsEqualApprox(WorldGen.Albedo(40f, 40f, 0f).R, WorldGen.AlbedoGen(40f, 40f, 0f, out _, out _).R)
                 && nz == 32 && GrassZone(2f, 2f, 1f) == 0f && GrassZone(40f, 40f, 1f) == 1f
                 && ScatterZone(22f, 2f, 0, 1f) == 0f && ScatterZone(22f, 2f, 1, 0.5f) == 0.5f;
        GD.Print($"terrain check: brushes on 4x4 vertices at the spawn -> {n} sculpted (ground +{lifted:F3} m), {np} painted "
                 + $"(colour {c0.R:F2},{c0.G:F2},{c0.B:F2} -> {col.R:F2},{col.G:F2},{col.B:F2}), {nz} zoned (grass there {GrassZone(2f, 2f, 1f)}, "
                 + $"trees 20 m on {ScatterZone(22f, 2f, 0, 1f)}); 40 m away untouched -> {(ok ? "PASS" : "FAIL")}");
        _dh = Sculpted(gen, regions, out _, out _);
        _paint = Painted(gc, regions, out _);
        _zone = Zoned(regions, out _);
    }

    private static void Backup()
    {
        var to = ProjectSettings.GlobalizePath("res://").PathJoin($"../scratch/bake_backup/{Time.GetDateStringFromSystem()}/terrain3d");
        DirAccess.MakeDirRecursiveAbsolute(to);
        foreach (var f in DirAccess.GetFilesAt(DataDir)) DirAccess.CopyAbsolute(ProjectSettings.GlobalizePath($"{DataDir}/{f}"), to.PathJoin(f));
        foreach (var f in new[] { Scene, RefHeight, RefColor })
            if (ResourceLoader.Exists(f)) DirAccess.CopyAbsolute(ProjectSettings.GlobalizePath(f), to.PathJoin(f.GetFile()));
    }
}
