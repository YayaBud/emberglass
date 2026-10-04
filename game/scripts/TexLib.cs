using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The world's surfaces: one shared material per generated texture set.
///
/// `scripts/forge/tex/texgen.py` writes `assets/tex/{name}_albedo|normal|orm.png`
/// at 52 texels per metre -- the sprite's own density (hd2d audit Law 2) -- and
/// this turns each set into one ORM material, built once and shared by every
/// mesh that asks for that name. A model built by the kit names its surfaces
/// (`brick`, `shingle`...) and never carries its own copy of a texture.
///
/// The PNGs are read raw rather than through the importer: Godot's default for
/// a texture it sees used in 3D is VRAM compression, and block compression
/// smears pixel art into mush. ponytail: raw loading does not survive an export
/// build as-is; add lossless .import settings when there is an export to ship.
/// </summary>
public static class TexLib
{
    public const float TexelsPerM = 52f;
    private const string Dir = "res://assets/tex/";

    private static readonly Dictionary<string, OrmMaterial3D> _mats = new();
    private static readonly Dictionary<string, Vector2I> _px = new();
    private static readonly Dictionary<string, Vector3> _mean = new();

    /// <summary>Whether a generated texture set exists under this name.</summary>
    public static bool Has(string surface) =>
        surface != "" && FileAccess.FileExists(Dir + surface + "_albedo.png");

    /// <summary>The shared material for a surface, UV-mapped (the kit's path).</summary>
    public static OrmMaterial3D Get(string surface)
    {
        if (_mats.TryGetValue(surface, out var m)) return m;
        var albedo = Load(Dir + surface + "_albedo.png", false, surface);
        _px[surface] = new Vector2I(albedo.GetWidth(), albedo.GetHeight());
        m = new OrmMaterial3D
        {
            ResourceName = "tex_" + surface,
            AlbedoTexture = albedo,
            NormalEnabled = true,
            NormalTexture = Load(Dir + surface + "_normal.png", true, null),
            OrmTexture = Load(Dir + surface + "_orm.png", false, null),
            // Nearest keeps every texel a crisp square, as the sprite's are;
            // the mipmaps stop a distant wall from shimmering.
            TextureFilter = Grade.SmoothTex ? BaseMaterial3D.TextureFilterEnum.LinearWithMipmapsAnisotropic : BaseMaterial3D.TextureFilterEnum.NearestWithMipmapsAnisotropic,
        };
        _mats[surface] = m;
        return m;
    }

    /// <summary>The same surface projected in world space at 52 texels/m, for
    /// geometry with no UVs of its own (the ground, the texture lab).</summary>
    public static OrmMaterial3D Triplanar(string surface)
    {
        var key = surface + "#tri";
        if (_mats.TryGetValue(key, out var m)) return m;
        m = (OrmMaterial3D)Get(surface).Duplicate();
        var rep = Repeat(surface);
        m.Uv1Triplanar = true;
        m.Uv1WorldTriplanar = true;
        m.Uv1TriplanarSharpness = 8f;
        // One repeat every (texture px / 52) metres. x and z take the width,
        // y the height; the tiles are within 2% of square, so a floor's v
        // (which rides z) is off by that much at worst.
        m.Uv1Scale = new Vector3(1f / rep.X, 1f / rep.Y, 1f / rep.X);
        _mats[key] = m;
        return m;
    }

    /// <summary>The surface on geometry whose UVs are in metres: one repeat
    /// per tile's metres. For a pattern that must follow the geometry, not
    /// the world axes (the city's setts run along each road).</summary>
    public static OrmMaterial3D Metres(string surface)
    {
        var key = surface + "#m";
        if (_mats.TryGetValue(key, out var m)) return m;
        m = (OrmMaterial3D)Get(surface).Duplicate();
        var rep = Repeat(surface);
        m.Uv1Scale = new Vector3(1f / rep.X, 1f / rep.Y, 1f);
        _mats[key] = m;
        return m;
    }

    private static Texture2D Load(string path, bool normal, string? meanOf)
    {
        var img = Image.LoadFromFile(ProjectSettings.GlobalizePath(path));
        if (meanOf != null) _mean[meanOf] = Mean(img);
        img.GenerateMipmaps(normal);
        return ImageTexture.CreateFromImage(img);
    }

    /// <summary>A surface's maps, for shaders that blend several (the ground).</summary>
    public static Texture2D Map(string surface, string map)
    {
        var m = Get(surface);
        return map switch { "albedo" => m.AlbedoTexture, "normal" => m.NormalTexture, _ => m.OrmTexture };
    }

    private static Godot.Collections.Dictionary? _manifest;

    /// <summary>Metres per repeat of a surface's tile, from texgen's manifest:
    /// most surfaces are drawn at 52 texels/m, the ground's HD set at 104.</summary>
    public static Vector2 Repeat(string surface)
    {
        _manifest ??= (Godot.Collections.Dictionary)Json.ParseString(
            FileAccess.GetFileAsString(Dir + "manifest.json"));
        var surfaces = (Godot.Collections.Dictionary)_manifest["surfaces"];
        var metres = (Godot.Collections.Array)((Godot.Collections.Dictionary)surfaces[surface])["metres"];
        return new Vector2((float)metres[0], (float)metres[1]);
    }

    /// <summary>The albedo's mean colour, linear: what a vertex tint is
    /// measured against, so a tint of exactly this colour changes nothing.</summary>
    public static Vector3 MeanLinear(string surface)
    {
        Get(surface);
        return _mean[surface];
    }

    private static Vector3 Mean(Image img)
    {
        if (img.GetFormat() != Image.Format.Rgb8) img.Convert(Image.Format.Rgb8);
        var d = img.GetData();
        double r = 0, g = 0, b = 0;
        var n = img.GetWidth() * img.GetHeight();
        for (var i = 0; i < n * 3; i += 3)
        {
            r += Lin(d[i]); g += Lin(d[i + 1]); b += Lin(d[i + 2]);
        }
        return new Vector3((float)(r / n), (float)(g / n), (float)(b / n));
    }

    private static double Lin(byte v)
    {
        var c = v / 255.0;
        return c <= 0.04045 ? c / 12.92 : System.Math.Pow((c + 0.055) / 1.055, 2.4);
    }

    // ---- the texture lab: `-- --texlab=N`, a harness, not the game ---------

    /// <summary>Surfaces in pages of six, as the lab shows them.</summary>
    public static readonly string[][] Pages =
    {
        new[] { "brick", "cobble", "fieldstone", "plaster", "planks", "timber" },
        new[] { "shingle", "slate", "fishscale", "thatch", "grass", "dirt" },
        new[] { "moss", "leaf_litter", "bark", "sand", "sandstone", "adobe" },
        new[] { "snow", "ice", "jungle_floor" },
    };

    private static readonly List<(string Name, MeshInstance3D Panel)> _lab = new();

    /// <summary>Stand one page of surfaces as wall panels across the road just
    /// past the spawn, facing the camera, at the player's depth -- the depth
    /// at which one texel is one screen pixel. The centre is left open for
    /// the character.</summary>
    public static void Lab(Node3D parent, int page)
    {
        var f = new Vector3(-0.7071f, 0f, -0.7071f);   // down the road (Village.F)
        var r = new Vector3(0.7071f, 0f, -0.7071f);    // screen-right (Village.R)
        float[] b = { -7.1f, -4.5f, -1.9f, 1.9f, 4.5f, 7.1f };
        var names = Pages[page];
        for (var i = 0; i < names.Length; i++)
        {
            var at = f * 3f + r * b[i];
            at.Y = WorldGen.Height(at.X, at.Z);
            var panel = new MeshInstance3D
            {
                Name = "Lab_" + names[i],
                Mesh = new BoxMesh { Size = new Vector3(2.4f, 2.2f, 0.3f) },
                MaterialOverride = Triplanar(names[i]),
                Position = at + Vector3.Up * 1.1f,
            };
            parent.AddChild(panel);
            // Face the camera: the box's +Z toward the viewer, who looks along f.
            panel.LookAt(panel.GlobalPosition + f, Vector3.Up);
            _lab.Add((names[i], panel));
        }
    }

    /// <summary>Each panel's front face as a screen rectangle, for the crop.</summary>
    public static void Report(Camera3D cam)
    {
        foreach (var (name, p) in _lab)
        {
            var c = p.GlobalPosition;
            var right = p.GlobalBasis.X * 1.2f;
            var up = Vector3.Up * 1.1f;
            var a = cam.UnprojectPosition(c - right + up);
            var d = cam.UnprojectPosition(c + right - up);
            GD.Print($"texlab {name} {Mathf.Min(a.X, d.X):F0} {Mathf.Min(a.Y, d.Y):F0} "
                     + $"{Mathf.Max(a.X, d.X):F0} {Mathf.Max(a.Y, d.Y):F0}");
        }
    }
}
