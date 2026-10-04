using System;
using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// The four regions that were bare ground (implementation_plan B3, user 2026-09-28: "ALL
/// BIOMES, THE GAME LOOKS DEAD AND DRY"), each one scene built once like
/// <see cref="SnowSite"/>, each with ONE rule of its own (the study's "one rule per place"):
///
/// * the Emberwood -- a woodcutter's glade under autumn trees: a giant fallen trunk, the
///   shed and the chopping block, a smoking charcoal mound, a lit shrine; squirrels, boar,
///   deer, a fox. Its rule: leaf litter and mushrooms (Scatter, Grass).
/// * Duskfen -- a boardwalk from the mud out over deep water to a stilt hut, the drowned
///   chapel standing in the water beyond, lily pads, reeds, willows and snags; herons, frogs,
///   ducks, wisps round the chapel. Its rule: water (the mud's drag and prints, the boardwalk).
/// * Elder Meadows -- a farmstead: the farmhouse, haystacks, a wheat field with a scarecrow,
///   beehives, stone walls, a sheep paddock; sheep, goats, hens, hares, crows. Its rule: wind.
/// * Greyward Crags -- the watchtower on the highest ground, cairns marking the way up, a mine
///   in a steep face with its cart; goats and crows. Its rule: height.
///
/// Every scene is found, not typed: a search over the real terrain at boot (the flattest
/// glade, the shoreline where dry mud meets deep water, the highest standable ground), so a
/// seed or terrain change moves the scene rather than burying it. The camera looks along F,
/// so each is composed as the frame reads it: the approach toward the lens kept open.
/// Scatter is kept off each site (it plants its own); grass is cleared under every building.
/// </summary>
public partial class RegionSites : Node3D
{
    private static readonly Vector2 F = new(-0.7071f, -0.7071f);
    private static readonly Vector2 R = new(0.7071f, -0.7071f);

    /// <summary>Each scene's centre and its landmark (the camera's reveal, the banner).</summary>
    public static readonly Dictionary<Biome, (Vector2 At, Vector2 Landmark)> Scenes = new();

    private readonly Dictionary<string, (Kit.Kind K, List<Kit.Item> Items)> _kit = new();
    private readonly List<Foliage.Spot> _plants = new();
    private readonly List<(Vector2 C, float R)> _solid = new();
    private readonly Random _rng = new(2828);
    private float U() => (float)_rng.NextDouble();
    private Node3D _player = null!;

    // ------------------------------------------------------------------ helpers
    private static float H(Vector2 p) => WorldGen.Height(p.X, p.Y);
    private static float Slope(Vector2 p) => 1f - WorldGen.Normal(p.X, p.Y).Y;

    /// <summary>The best-scoring point on a grid within `r` of `c` (NaN score = never).</summary>
    private static Vector2 Best(Vector2 c, float r, float step, Func<Vector2, float> score)
    {
        var best = c;
        var bs = float.MinValue;
        for (var z = -r; z <= r; z += step)
        for (var x = -r; x <= r; x += step)
        {
            if (x * x + z * z > r * r) continue;
            var p = c + new Vector2(x, z);
            var s = score(p);
            if (!float.IsNaN(s) && s > bs) { bs = s; best = p; }
        }
        return best;
    }

    /// <summary>Queue a kit asset; a building's footprint clears the grass and blocks animals.</summary>
    private void Put(string asset, Vector2 p, float yaw, Kit.Kind kind, float scale = 1f, float? y = null)
    {
        if (!_kit.TryGetValue(asset, out var e)) _kit[asset] = e = (kind, new List<Kit.Item>());
        var foot = new Vector3(p.X, y ?? H(p), p.Y);
        var snow = Biomes.WeightOf(Biome.Snow, p, WorldGen.Seed);
        e.Items.Add(new Kit.Item(foot, yaw, scale, snow < 0.05f ? 0f : snow));
        if (kind is Kit.Kind.Rock)
        {
            var box = Kit.Box(asset);
            var basis = new Basis(Vector3.Up, yaw);
            var c = foot + basis * (box.GetCenter() * scale);
            var ax = basis.X;
            var half = new Vector2(box.Size.X, box.Size.Z) * 0.5f * scale;
            Grass.ClearBox(new Vector2(c.X, c.Z), new Vector2(ax.X, ax.Z), half, 0.8f);
            _solid.Add((new Vector2(c.X, c.Z), Mathf.Min(half.X, half.Y) * 0.9f));
        }
    }

    private void Plant(string kind, Vector2 p, float scale, bool shadow) =>
        _plants.Add(new Foliage.Spot(kind, new Vector3(p.X, H(p), p.Y), scale, shadow));

    private void Lamp(Vector3 at, float strength = 1.8f, float reach = 9f) =>
        Bake.Lamp(this, new LampLight { Name = "Lamp", Position = at, Fire = true, Strength = strength, Reach = reach }, auto: true);

    /// <summary>A world position on an asset, from its local (x, y up, z front) offset.</summary>
    private static Vector3 On(Vector2 foot, float yaw, Vector3 local, float? y = null) =>
        new Vector3(foot.X, y ?? H(foot), foot.Y) + new Basis(Vector3.Up, yaw) * local;

    /// <summary>A fauna of this site: animals kept inside the disc (c, r), walking round the
    /// site's buildings and the trunks of its trees.</summary>
    private Fauna Animals(string name, Vector2 c, float r, int seed, Func<Vector2, bool>? dry = null)
    {
        var fauna = new Fauna
        {
            Name = name,
            Keep = p => (p - c).Length() <= r ? p : c + (p - c).Normalized() * r,
        };
        if (dry != null) fauna.Dry = dry;
        AddChild(fauna);
        fauna.Bind(_player, seed);
        return fauna;
    }

    private List<Vector2> Homes(Vector2 c, float r, int n, Func<Vector2, bool>? ok = null)
    {
        var l = new List<Vector2>();
        for (var i = 0; i < n * 8 && l.Count < n; i++)
        {
            var t = U() * Mathf.Tau;
            var p = c + new Vector2(Mathf.Cos(t), Mathf.Sin(t)) * r * Mathf.Sqrt(U());
            if (ok == null || ok(p)) l.Add(p);
        }
        return l;
    }

    /// <summary>A smoke column (the charcoal clamp's vent): slow grey puffs, drifting downwind.</summary>
    private void Smoke(Vector3 at)
    {
        if (!Bake.Emitter("smoke", ref at)) return;
        var puff = new StandardMaterial3D
        {
            Transparency = BaseMaterial3D.TransparencyEnum.Alpha,
            AlbedoColor = new Color(0.55f, 0.52f, 0.5f, 0.35f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            VertexColorUseAsAlbedo = true,
        };
        var fade = new Gradient();
        fade.SetColor(0, new Color(1f, 1f, 1f, 0.7f));
        fade.SetColor(1, new Color(1f, 1f, 1f, 0f));
        AddChild(new GpuParticles3D
        {
            Name = "Smoke", Position = at, Amount = 40, Lifetime = 7.0, Preprocess = 7.0,
            ProcessMaterial = new ParticleProcessMaterial
            {
                Direction = new Vector3(Surface.WindDir.X * 0.3f, 1f, Surface.WindDir.Y * 0.3f), Spread = 10f,
                InitialVelocityMin = 0.5f, InitialVelocityMax = 0.8f, Gravity = new Vector3(Surface.WindDir.X * 0.15f, 0.05f, Surface.WindDir.Y * 0.15f),
                ScaleMin = 0.8f, ScaleMax = 1.4f, ColorRamp = new GradientTexture1D { Gradient = fade },
            },
            DrawPass1 = new QuadMesh { Size = new Vector2(0.7f, 0.7f), Material = puff },
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            VisibilityAabb = new Aabb(new Vector3(-8f, -1f, -8f), new Vector3(16f, 16f, 16f)),
        });
    }

    /// <summary>Wisps: a few cold lights drifting slowly round a point (the drowned chapel).</summary>
    private void Wisps(Vector3 at)
    {
        if (!Bake.Emitter("wisps", ref at)) return;
        var glow = new StandardMaterial3D
        {
            ShadingMode = BaseMaterial3D.ShadingModeEnum.Unshaded,
            AlbedoColor = new Color(0.55f, 0.95f, 1f),
            BillboardMode = BaseMaterial3D.BillboardModeEnum.Enabled,
        };
        AddChild(new GpuParticles3D
        {
            Name = "Wisps", Position = at, Amount = 10, Lifetime = 9.0, Preprocess = 9.0,
            ProcessMaterial = new ParticleProcessMaterial
            {
                EmissionShape = ParticleProcessMaterial.EmissionShapeEnum.Box,
                EmissionBoxExtents = new Vector3(6f, 1.2f, 6f), Spread = 180f,
                InitialVelocityMin = 0.05f, InitialVelocityMax = 0.2f, Gravity = Vector3.Zero,
                TurbulenceEnabled = true, TurbulenceNoiseStrength = 0.6f, TurbulenceInfluenceMin = 0.02f, TurbulenceInfluenceMax = 0.05f,
            },
            DrawPass1 = new QuadMesh { Size = new Vector2(0.09f, 0.09f), Material = glow },
            CastShadow = GeometryInstance3D.ShadowCastingSetting.Off,
            VisibilityAabb = new Aabb(new Vector3(-10f, -3f, -10f), new Vector3(20f, 8f, 20f)),
        });
        AddChild(new OmniLight3D { Position = at + Vector3.Up * 0.8f, LightColor = new Color(0.5f, 0.9f, 1f), LightEnergy = 0.8f, OmniRange = 7f });
    }

    /// <summary>A ring of trees round `c` between r0 and r1, the lens side left open.</summary>
    private void Ring(Vector2 c, float r0, float r1, int n, string[] trees, string[] under, Func<Vector2, bool>? ok = null)
    {
        for (var i = 0; i < n; i++)
        {
            var t = U() * Mathf.Tau;
            var p = c + new Vector2(Mathf.Cos(t), Mathf.Sin(t)) * Mathf.Lerp(r0, r1, U());
            var rel = p - c;
            if (rel.Dot(-F) > 6f && Mathf.Abs(rel.Dot(R)) < 11f) continue;   // the approach from the camera
            if (Slope(p) > 0.3f || (ok != null && !ok(p))) continue;
            Plant(trees[(int)(U() * trees.Length) % trees.Length], p, 0.85f + U() * 0.4f, true);
            if (U() < 0.7f)
                Plant(under[(int)(U() * under.Length) % under.Length], p + new Vector2(U() - 0.5f, U() - 0.5f) * 3f, 0.8f + U() * 0.5f, false);
        }
    }

    // ------------------------------------------------------------------ build
    public void Build(Node3D player)
    {
        _player = player;
        Ember();
        Fen();
        Meadow();
        Crags();
        var placed = 0;
        foreach (var (asset, (kind, items)) in _kit) placed += Kit.Place(this, asset, items, kind);
        Wildwood.Tiled(this, _plants);
        GD.Print($"regionsites: {placed} kit pieces, {_plants.Count} plants; " +
                 string.Join(", ", Scenes.Select(kv => $"{kv.Key} at ({kv.Value.At.X:F0},{kv.Value.At.Y:F0})")));
    }

    private void Blockers(Fauna f)
    {
        foreach (var (c, r) in _solid) f.Block(c, r);
        Wildwood.Blockers(f, _plants);
    }

    // ------------------------------------------------------------ the Emberwood
    private void Ember()
    {
        // the flattest glade near the region's middle
        var s = Best(new Vector2(230f, -210f), 60f, 4f, p =>
            -(Slope(p) + Slope(p + F * 8f) + Slope(p - F * 8f) + Slope(p + R * 8f) + Slope(p - R * 8f)) * 10f
            - (p - new Vector2(230f, -210f)).Length() * 0.01f);
        var shrine = s + F * 18f + R * 3f;
        Scenes[Biome.Emberwood] = (s, shrine);
        Scatter.Keep(s, 34f);
        Put("TrunkArch", s + F * 6f, Kit.Along(R), Kit.Kind.Prop);
        var shed = s - R * 9f + F * 1f;
        Put("WoodShed", shed, Kit.Facing(-F), Kit.Kind.Rock);
        Lamp(On(shed, Kit.Facing(-F), new Vector3(0f, 2.1f, -1.3f)), 1.5f, 8f);
        Put("ChoppingBlock", s - R * 6f - F * 2.5f, 0.4f, Kit.Kind.Prop);
        Put("LogPile", s - R * 12.5f - F * 1.5f, Kit.Along(F), Kit.Kind.Prop);
        Put("Stump", s - R * 4f + F * 3.5f, 0f, Kit.Kind.Prop);
        var mound = s + R * 9f - F * 1f;
        Put("CharcoalMound", mound, 0.3f, Kit.Kind.Rock);
        Smoke(new Vector3(mound.X, H(mound) + 1.6f, mound.Y));
        Put("Shrine", shrine, Kit.Facing(-F), Kit.Kind.Rock);
        Lamp(new Vector3(shrine.X, H(shrine) + 0.8f, shrine.Y), 1.2f, 6f);
        Breakables.Add("Barrel", shed + R * 2.6f - F * 1.8f, 0.3f);
        Breakables.Add("Barrel", shed + R * 3.3f - F * 1.1f, 1.1f);
        Breakables.Add("Crate", shed - R * 2.6f - F * 1.9f, 0.2f);
        Breakables.Add("Pot", shrine - F * 1.6f + R * 1.1f, 0.5f);
        Ring(s, 13f, 30f, 90, new[] { "autumn_oak", "autumn_oak", "autumn_birch", "oak" }, new[] { "fern", "mushroom", "bush", "fern" });
        for (var i = 0; i < 14; i++)
        {
            var p = s + new Vector2(U() - 0.5f, U() - 0.5f) * 24f;
            if ((p - s).Length() > 5f) Plant(U() < 0.6f ? "mushroom" : "fern", p, 0.8f + U() * 0.5f, false);
        }
        var f = Animals("EmberFauna", s, 30f, 5151);
        f.Add(new Fauna.Kind("squirrel", 1.4f, 6f, 5f, 7f, 0.28f, 0.18f, "sit"), Homes(s, 22f, 6));
        f.Add(new Fauna.Kind("boar", 0.8f, 6.5f, 7f, 10f, 0.3f, 0.45f, "sniff"), Homes(s + F * 12f, 8f, 2));
        f.Add(new Fauna.Kind("doe", 1.1f, 7.5f, 11f, 8f, 0.34f, 0.45f, "graze"), Homes(s + F * 10f - R * 10f, 6f, 3));
        f.Add(new Fauna.Kind("fox", 1.7f, 6.5f, 8f, 16f, 0.22f, 0.3f, "sniff"), Homes(s, 18f, 1));
        Blockers(f);
    }

    // ------------------------------------------------------------------ Duskfen
    private void Fen()
    {
        var c0 = new Vector2(-90f, 300f);
        var w = WorldGen.FenWaterLevel;
        // the shore: dry mud here, the land behind it (toward the lens) dry, deep water ahead
        var e = Best(c0, 95f, 3f, p =>
        {
            var h = H(p);
            if (h < w + 0.15f || h > w + 0.8f || H(p - F * 6f) < w + 0.1f || H(p + F * 16f) > w - 0.9f) return float.NaN;
            return -(p - c0).Length();
        });
        var chapel = e + F * 30f + R * 12f;
        Scenes[Biome.Fen] = (e, chapel);
        Scatter.Keep(e + F * 14f, 40f);
        var yaw = Kit.Along(F);
        var body = new StaticBody3D { Name = "Boardwalk_Solid" };
        AddChild(body);
        for (var i = 0; i < 5; i++)
        {
            var at = e + F * (2f + 4f * i);
            Put("Boardwalk", at, yaw, Kit.Kind.Prop, 1f, w);
            // the deck's own collider: its top is the planks' (0.435 over the water)
            body.AddChild(new CollisionShape3D
            {
                Shape = new BoxShape3D { Size = new Vector3(4.05f, 0.11f, 1.4f) },
                Transform = new Transform3D(new Basis(Vector3.Up, yaw), new Vector3(at.X, w + 0.38f, at.Y)),
            });
        }
        var hut = e + F * 23.5f;
        var hy = Kit.Facing(-F);
        Put("StiltHut", hut, hy, Kit.Kind.Prop, 1f, w);
        body.AddChild(new CollisionShape3D   // the platform, a jump up from the walk
        {
            Shape = new BoxShape3D { Size = new Vector3(3.8f, 0.15f, 3.4f) },
            Transform = new Transform3D(new Basis(Vector3.Up, hy), new Vector3(hut.X, w + 1.0f, hut.Y)),
        });
        body.AddChild(new CollisionShape3D   // the walls
        {
            Shape = new BoxShape3D { Size = new Vector3(3.0f, 1.7f, 2.4f) },
            Transform = new Transform3D(new Basis(Vector3.Up, hy), On(hut, hy, new Vector3(0f, 1.93f, -0.3f), w)),
        });
        Lamp(On(hut, hy, new Vector3(-0.8f, 2.4f, 1.2f), w), 1.8f, 9f);
        Lamp(new Vector3(e.X, H(e) + 1.6f, e.Y) + new Vector3(R.X, 0f, R.Y) * 1.2f, 1.3f, 7f);
        Put("Lantern", e + R * 1.2f, Kit.Facing(-F), Kit.Kind.Prop);
        Put("DrownedChapel", chapel, Kit.Facing(-F), Kit.Kind.Rock);
        Wisps(new Vector3(chapel.X, w + 0.7f, chapel.Y) - new Vector3(F.X, 0f, F.Y) * 5f);
        for (var i = 0; i < 40; i++)
        {
            var p = e + F * (6f + U() * 34f) + R * ((U() - 0.5f) * 36f);
            if (H(p) < w - 0.5f && (p - hut).Length() > 4f && (p - chapel).Length() > 5f && Mathf.Abs((p - e).Dot(R)) > 1.8f)
                Put("LilyPads", p, U() * Mathf.Tau, Kit.Kind.Prop, 0.8f + U() * 0.5f, w + 0.005f);
        }
        Breakables.Add("Pot", e - F * 2.5f - R * 1.8f, 0.4f);
        Breakables.Add("Jar", e - F * 3.2f - R * 2.6f, 1.3f);
        Breakables.Add("Barrel", e - F * 2f + R * 2.4f, 0.8f);
        // reeds all along the waterline, snags and willows on the mud behind
        for (var i = 0; i < 260; i++)
        {
            var p = e + new Vector2(U() - 0.5f, U() - 0.5f) * 80f;
            var h = H(p);
            if (Mathf.Abs((p - e).Dot(R)) < 2.2f && (p - e).Dot(F) > -4f) continue;   // the walk
            if (h > w - 0.7f && h < w + 0.35f) Plant("reed", p, 0.8f + U() * 0.5f, false);
            else if (h >= w + 0.35f && U() < 0.25f) Plant(U() < 0.5f ? "snag" : "willow", p, 0.85f + U() * 0.35f, true);
            else if (h >= w + 0.35f && U() < 0.2f) Plant(U() < 0.6f ? "bush" : "mushroom", p, 0.8f + U() * 0.4f, false);
        }
        var f = Animals("FenFauna", e + F * 12f, 36f, 6262, dry: p => H(p) > w - 0.5f);
        f.Deep = p => H(p) < w - 0.4f;
        f.Water = w;
        f.Ripple = Water.Ripple;
        f.Add(new Fauna.Kind("heron", 0.5f, 5f, 7f, 8f, 0.3f, 0.25f, "fish", Flies: true), Homes(e + F * 8f, 14f, 3, p => H(p) > w - 0.5f && H(p) < w + 0.3f));
        f.Add(new Fauna.Kind("frog", 0.6f, 3f, 2.5f, 4f, 0.2f, 0.12f, "sit"), Homes(e, 12f, 8, p => H(p) > w && H(p) < w + 0.6f));
        f.Add(new Fauna.Kind("duck", 0.45f, 4f, 5f, 8f, 0.18f, 0.3f, "dabble", Flies: true, On: Fauna.Medium.Swim), Homes(e + F * 20f, 12f, 5, p => H(p) < w - 0.5f));
        Blockers(f);
    }

    // ---------------------------------------------------------- Elder Meadows
    private void Meadow()
    {
        var c0 = new Vector2(-250f, -150f);
        var s = Best(c0, 60f, 4f, p =>
            -(Slope(p) + Slope(p + R * 14f) + Slope(p + R * 24f) + Slope(p + F * 12f) + Slope(p - R * 10f)) * 10f
            - (p - c0).Length() * 0.01f);
        var house = s - R * 7f + F * 6f;
        Scenes[Biome.Meadow] = (s, house);
        Scatter.Keep(s + R * 6f, 42f);
        var hy = Kit.Facing(-F);
        Put("Farmhouse", house, hy, Kit.Kind.Rock);
        Lamp(On(house, hy, new Vector3(0.4f, 2.3f, 2.8f)), 1.6f, 9f);
        foreach (var d in new[] { 2f, 6.5f, 11f })
            Put("Haystack", s + R * 8f + F * d, U() * Mathf.Tau, Kit.Kind.Rock, 0.85f + U() * 0.3f);
        foreach (var (a, b) in new[] { (6.5f, 4f), (7.3f, 5f), (9.6f, 8.5f), (10.2f, 3f) })
            Breakables.Add("HayBale", s + R * a + F * b, Kit.Along(R) + (U() - 0.5f) * 0.4f);
        Breakables.Add("Barrel", house + R * 4.2f - F * 2.2f, 0.2f);
        Breakables.Add("Crate", house + R * 4.6f - F * 3.2f, 0.7f);
        Put("Beehives", s - R * 13f - F * 1f, hy, Kit.Kind.Prop);
        // the wheat field, a scarecrow in it
        var field = s + R * 20f + F * 5f;
        for (var a = -8f; a <= 8f; a += 1.05f)
        for (var b = -9f; b <= 9f; b += 1.05f)
        {
            var p = field + R * (a + (U() - 0.5f) * 0.5f) + F * (b + (U() - 0.5f) * 0.5f);
            if (Mathf.Abs(a) < 1.2f && Mathf.Abs(b) < 1.2f) continue;
            Plant("wheat", p, 0.9f + U() * 0.3f, false);
        }
        Put("Scarecrow", field, Kit.Facing(-F), Kit.Kind.Prop);
        Grass.ClearBox(field, R, new Vector2(8.5f, 9.5f), 0.6f);
        // stone walls along the field's near edge, a fenced paddock beyond the house
        var wall = Kit.Box("StoneWall").Size.X;
        for (var i = 0; i < 5; i++) Put("StoneWall", field - F * 11f + R * ((i - 2) * wall * 0.98f), Kit.Along(R), Kit.Kind.Rock);
        var pad = s + F * 18f - R * 7f;
        var fence = Kit.Box("Fence").Size.X;
        var posts = new List<(Vector2 A, Vector2 B)>();
        for (var i = 0; i < 16; i++)
        {
            float t0 = i / 16f * Mathf.Tau, t1 = (i + 1) / 16f * Mathf.Tau;
            var a = pad + new Vector2(Mathf.Cos(t0), Mathf.Sin(t0)) * 7.5f;
            var b = pad + new Vector2(Mathf.Cos(t1), Mathf.Sin(t1)) * 7.5f;
            if (i == 11) continue;   // the gate
            Put("Fence", (a + b) / 2f, Kit.Along(b - a), Kit.Kind.Prop, (b - a).Length() / fence);
            posts.Add((a, b));
        }
        for (var i = 0; i < 70; i++)
        {
            var p = s + new Vector2(U() - 0.5f, U() - 0.5f) * 70f;
            if ((p - field).Length() < 13f || (p - house).Length() < 6f || (p - pad).Length() < 9f) continue;
            Plant(U() < 0.7f ? "flowers" : "bush", p, 0.9f + U() * 0.5f, false);
        }
        Plant("oak", house - R * 7f + F * 2f, 1.25f, true);
        Plant("oak", s + R * 34f + F * 20f, 1.2f, true);
        var sheep = Animals("PaddockFauna", pad, 6.3f, 7171);
        sheep.Add(new Fauna.Kind("sheep", 0.5f, 3.5f, 1.2f, 6f, 0.28f, 0.4f, "graze", Pet: true), Homes(pad, 5f, 6));
        foreach (var (a, b) in posts) sheep.BlockLine(a, b, 0.2f);
        var f = Animals("MeadowFauna", s + R * 6f, 40f, 7272);
        f.Add(new Fauna.Kind("goat", 0.6f, 4f, 1.2f, 8f, 0.3f, 0.35f, "graze", Pet: true), Homes(s - R * 4f + F * 14f, 6f, 2));
        f.Add(new Fauna.Kind("hen", 0.5f, 3.5f, 2.2f, 4f, 0.12f, 0.15f, "peck"), Homes(house + R * 5f - F * 4f, 3f, 4));
        f.Add(new Fauna.Kind("hare", 1.5f, 7f, 6f, 10f, 0.3f, 0.2f, "sit"), Homes(s + R * 28f, 12f, 3));
        f.Add(new Fauna.Kind("crow", 0.5f, 6f, 4.5f, 8f, 0.12f, 0.18f, "peck", Flies: true), Homes(field, 7f, 7));
        Blockers(f);
        foreach (var (a, b) in posts) f.BlockLine(a, b, 0.2f);
    }

    // ---------------------------------------------------------- Greyward Crags
    private void Crags()
    {
        var c0 = new Vector2(-260f, 250f);
        // the highest ground a tower can stand on
        var top = Best(c0, 80f, 4f, p => Slope(p) > 0.22f ? float.NaN : H(p) - (p - c0).Length() * 0.02f);
        Scenes[Biome.Crags] = (top, top);
        Scatter.Keep(top, 22f);
        var ty = Kit.Facing(-F);
        Put("Watchtower", top, ty, Kit.Kind.Rock);
        Lamp(On(top, ty, new Vector3(0f, 2.3f, 2.9f)), 1.6f, 9f);
        Lamp(On(top, ty, new Vector3(0f, 7.0f, 2.5f)), 1.0f, 6f);
        Breakables.Add("Crate", top - F * 4f + R * 2.5f, 0.3f);
        Breakables.Add("Barrel", top - F * 4.6f + R * 3.4f, 1.2f);
        // cairns down the way the camera comes up
        for (var i = 1; i <= 5; i++)
        {
            var p = top - F * (9f * i) + R * ((U() - 0.5f) * 6f);
            if (Slope(p) < 0.35f) Put("Cairn", p, U() * Mathf.Tau, Kit.Kind.Rock, 0.9f + U() * 0.3f);
        }
        // the mine: a steep face within 45 m, the mouth looking down it
        var mine = Best(top, 45f, 3f, p =>
        {
            var s = Slope(p);
            return s < 0.3f || s > 0.6f || (p - top).Length() < 14f ? float.NaN : s - (p - top).Length() * 0.005f;
        });
        var n = WorldGen.Normal(mine.X, mine.Y);
        var down = new Vector2(n.X, n.Z).Normalized();
        var my = Kit.Facing(down);
        Put("MineMouth", mine, my, Kit.Kind.Rock);
        Put("Minecart", mine + down * 4f, Kit.Along(down), Kit.Kind.Rock);
        Lamp(On(mine, my, new Vector3(1.4f, 2.2f, 1.2f)), 1.4f, 8f);
        Breakables.Add("Crate", mine + down * 3.5f + new Vector2(-down.Y, down.X) * 2.2f, 0.4f);
        foreach (var (asset, k) in new[] { ("RockLarge", 5), ("RockMedium", 8) })
            for (var i = 0; i < k; i++)
            {
                var p = top + new Vector2(U() - 0.5f, U() - 0.5f) * 44f;
                if ((p - top).Length() > 7f && (p - mine).Length() > 6f) Put(asset, p, U() * Mathf.Tau, Kit.Kind.Rock, 0.8f + U() * 0.5f);
            }
        Ring(top, 10f, 28f, 50, new[] { "pine", "pine", "birch" }, new[] { "heather", "heather", "fern" });
        var f = Animals("CragFauna", top, 30f, 8282);
        f.Add(new Fauna.Kind("goat", 0.6f, 4.5f, 4f, 10f, 0.3f, 0.35f, "graze", Pet: true), Homes(top, 20f, 5, p => Slope(p) < 0.45f));
        f.Add(new Fauna.Kind("crow", 0.5f, 6f, 4.5f, 8f, 0.12f, 0.18f, "peck", Flies: true), Homes(top, 12f, 5));
        Blockers(f);
    }
}
