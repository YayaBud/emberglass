using System.Collections.Generic;
using System.Text.Json;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The player's picture: 8 facings x 13 actions of packed sprite strips, loaded
/// from the forge's manifest and drawn on one upright quad.
///
/// The manifest is the only contract between Blender and the game. Nothing here
/// hardcodes a frame count, a canvas size or the bake elevation -- those change
/// every time the forge runs, and a second copy of them is a second thing to
/// forget to update.
/// </summary>
public partial class SpriteRig : Node3D
{
    /// <summary>Animation frames per second. Independent of physics: a sprite
    /// clock tied to the frame rate speeds the walk up on a faster machine.</summary>
    public const float Fps = 12f;

    /// <summary>The two bakes of the cast. The pitch is welded to the bake (D1),
    /// so a hybrid camera needs the character drawn at both of its angles: LOW
    /// for the outskirts, TOP for everywhere else.</summary>
    private const string LowDir = "res://assets/sprites/";
    private const string TopDir = "res://assets/sprites_td/";

    /// <summary>One bake: its strips and the numbers its manifest carries.</summary>
    private sealed class Set
    {
        public readonly Dictionary<string, (Texture2D Tex, int Frames)> Strips = new();
        public int CanvasPx = 128, SpritePx = 96, FootPx;
        public readonly Dictionary<string, int> FootByFacing = new();
        public float BakeDeg = 8f, WorldH = 1.85f;
    }

    private Set _low = null!, _top = null!, _set = null!;
    private Dictionary<string, (Texture2D Tex, int Frames)> _strips = new();
    private Node3D _pivot = null!;
    private MeshInstance3D _quad = null!;
    private StandardMaterial3D _mat = null!;

    private string _action = "idle";
    private int _facing;
    private float _clock;
    private int _frame;

    public int CanvasPx => _set.CanvasPx;
    public int SpritePx => _set.SpritePx;
    public float WorldH => _set.WorldH;
    /// <summary>Empty canvas rows under the lowest foot, from the manifest.</summary>
    public int FootPx => _set.FootPx;
    /// <summary>The angles the two sets were baked at; the camera blends between
    /// exactly these.</summary>
    public float LowDeg => _low.BakeDeg;
    public float TopDeg => _top.BakeDeg;
    public bool IsTop => _set == _top;

    /// <summary>True once the current action has played its last frame. A
    /// one-shot state (land, an attack, hurt) ends on this rather than on a
    /// timer, so the animation and the state machine cannot disagree.</summary>
    public bool Finished { get; private set; }

    public static readonly string[] Facings =
        { "s", "sw", "w", "nw", "n", "ne", "e", "se" };

    public override void _Ready()
    {
        // --sprites=<dir> forces ONE set for both slots -- the A/B harness.
        string? only = null;
        foreach (var a in OS.GetCmdlineUserArgs())
            if (a.StartsWith("--sprites=")) only = a[10..].TrimEnd('/') + "/";

        _low = LoadManifest(only ?? LowDir) ?? new Set();
        _top = only != null ? _low : LoadManifest(TopDir) ?? _low;
        _set = _top;
        _strips = _set.Strips;

        _mat = new StandardMaterial3D
        {
            // Alpha-scissor, never alpha-blend. Blending writes no depth, so a
            // blended sprite sorts against the world per-object and pops in
            // front of whatever it is standing behind.
            Transparency = BaseMaterial3D.TransparencyEnum.AlphaScissor,
            AlphaScissorThreshold = 0.5f,
            TextureFilter = BaseMaterial3D.TextureFilterEnum.Nearest,
            CullMode = BaseMaterial3D.CullModeEnum.Disabled,
            // The figure carries its own painted light from the bake. Lighting
            // it again in-engine double-shades it and the palette goes muddy.
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            AlbedoColor = Grade.SpriteModulate(),
        };

        var h = WorldH * CanvasPx / SpritePx;
        // The tilt happens about the FEET, not about the middle of the picture.
        // A quad rotated about its own centre swings its bottom edge away from
        // the ground, and the character then slides up or down the slope of the
        // tilt as the pitch changes.
        _pivot = new Node3D { Name = "Pivot" };
        AddChild(_pivot);

        // ...and the feet are not at the bottom of the canvas. The figure is
        // drawn 45 px tall inside 64 px with headroom for the raised sword, so
        // aligning the quad's bottom edge to the ground left the character
        // hanging in the air with its shadow underneath it.
        _quad = new MeshInstance3D
        {
            Name = "Quad",
            Mesh = new QuadMesh { Size = new Vector2(h, h) },
            MaterialOverride = _mat,
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
        };
        _pivot.AddChild(_quad);
        Anchor();

        Play("idle", 0, true);
    }

    private static Set? LoadManifest(string dir)
    {
        using var f = FileAccess.Open(dir + "manifest.json", FileAccess.ModeFlags.Read);
        if (f == null)
        {
            GD.PushWarning("SpriteRig: no manifest at " + dir + " -- run pack_sheets.py");
            return null;
        }

        using var doc = JsonDocument.Parse(f.GetAsText());
        var root = doc.RootElement;
        var set = new Set
        {
            CanvasPx = root.GetProperty("canvas_px").GetInt32(),
            SpritePx = root.GetProperty("sprite_px").GetInt32(),
            BakeDeg = (float)root.GetProperty("bake_deg").GetDouble(),
            WorldH = (float)root.GetProperty("world_h").GetDouble(),
        };
        if (root.TryGetProperty("foot_px", out var fp)) set.FootPx = fp.GetInt32();
        if (root.TryGetProperty("foot_by_facing", out var fbf))
            foreach (var e in fbf.EnumerateObject()) set.FootByFacing[e.Name] = e.Value.GetInt32();

        foreach (var s in root.GetProperty("strips").EnumerateObject())
        {
            var file = s.Value.GetProperty("file").GetString()!;
            var tex = GD.Load<Texture2D>(dir + file);
            if (tex == null) continue;
            set.Strips[s.Name] = (tex, s.Value.GetProperty("frames").GetInt32());
        }

        GD.Print($"sprites: {dir} {set.Strips.Count} strips, bake {set.BakeDeg}deg, foot {set.FootPx}px");
        return set;
    }

    /// <summary>Show the LOW or the TOP bake. Called by the player at the
    /// midpoint of a camera blend; keeps the current action, frame and facing.</summary>
    public void UseTop(bool top)
    {
        var want = top ? _top : _low;
        if (want == _set) return;
        _set = want;
        _strips = _set.Strips;
        Anchor();
        Apply();
    }

    /// <summary>Put the feet on the ground for the active set. The two bakes
    /// leave different empty rows under the feet (16 px at 8 deg, 19 at 38), so
    /// a swap that kept the old anchor would lift or sink the character.</summary>
    private void Anchor()
    {
        var h = WorldH * CanvasPx / SpritePx;
        var px = _set.FootByFacing.TryGetValue(Facings[_facing], out var f) ? f : FootPx;
        var foot = h * px / CanvasPx;
        _quad.Position = new Vector3(0f, h * 0.5f - foot, 0f);
    }

    /// <summary>Aim the picture at the camera: yaw to face it, then lie back by
    /// the pitch, rotating about the feet.
    ///
    /// The sign of the pitch is NEGATIVE and that is not cosmetic. Godot's
    /// Rx(+p) tips a quad's normal DOWNWARD, so tilting by +pitch leaned the
    /// picture away from a camera that was already looking down: the sprite
    /// rendered at cos(2 x 26) = 0.62 of its height, which is exactly the "why
    /// is the character so small" the first build showed. Rx(-p) points the
    /// normal at the camera and the figure renders at its authored size.
    /// </summary>
    public void SetTilt(float pitchRad, float yawRad) =>
        _pivot.Rotation = new Vector3(-pitchRad, yawRad, 0f);

    /// <summary>Squash and stretch, applied to the QUAD and not baked into the
    /// art -- 13 actions x 8 facings is 104 strips to re-render otherwise.</summary>
    public void SetSquash(float x, float y) => _pivot.Scale = new Vector3(x, y, 1f);

    public void SetFacing(int facing)
    {
        if (facing == _facing) return;
        _facing = facing;
        Anchor();
        Apply();
    }

    public void Play(string action, int facing, bool restart = false)
    {
        if (facing != _facing) { _facing = facing; Anchor(); }
        if (!restart && action == _action) return;
        _action = action;
        _clock = 0f;
        _frame = 0;
        Finished = false;
        Apply();
    }

    public override void _Process(double delta)
    {
        if (_strips.Count == 0) return;
        if (!_strips.TryGetValue(Key(), out var strip)) return;

        _clock += (float)delta * Fps;
        var f = Mathf.FloorToInt(_clock);
        if (f >= strip.Frames)
        {
            Finished = true;
            // Loops carry on; one-shots hold their last frame until the state
            // machine moves off them.
            if (Loops(_action)) { _clock -= strip.Frames; f = 0; }
            else f = strip.Frames - 1;
        }

        if (f == _frame) return;
        _frame = f;
        Apply();
    }

    private static bool Loops(string action) =>
        action is "idle" or "walk" or "run" or "fall" or "dive";

    private string Key() => $"{_action}_{Facings[_facing]}";

    private void Apply()
    {
        if (!_strips.TryGetValue(Key(), out var strip)) return;
        _mat.AlbedoTexture = strip.Tex;
        // One frame of the strip, selected by scaling the UV to 1/frames and
        // sliding it along.
        _mat.Uv1Scale = new Vector3(1f / strip.Frames, 1f, 1f);
        _mat.Uv1Offset = new Vector3((float)Mathf.Min(_frame, strip.Frames - 1)
                                     / strip.Frames, 0f, 0f);
    }
}
