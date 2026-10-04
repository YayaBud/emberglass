using System;
using System.Collections.Generic;
using System.Linq;
using Godot;

namespace Worldbuilder;

/// <summary>
/// People (user, 2026-09-26: "make the game more livable ... different
/// characters npcs fill the world"): the ten townsfolk from
/// `scripts/forge/folk/` walking routes, pausing, standing about in squares,
/// and talking when the player presses E beside them (<see cref="Interact"/>).
///
/// Drawn exactly like the player: unshaded pixel art baked at both camera
/// angles (the set follows <see cref="CameraRig.TopSet"/>), tilted by MINUS
/// the pitch about the feet, facing picked with the player's own
/// <see cref="CameraRig.FacingFor"/>, and the region's exposure cancelled
/// (<see cref="Weather.FigureKeep"/>). One MultiMesh per person-type plus a
/// sun-facing shadow caster; frame and facing in each instance's custom data.
/// Moved in `_Process`, so the MultiMesh nodes opt out of physics
/// interpolation (INVARIANTS: Traps).
/// </summary>
public partial class Townsfolk : Node3D
{
    private const string Dir = "res://assets/folk/";
    /// <summary>Past this the people are hidden and only stepped now and then.</summary>
    private const float Near = 110f;
    /// <summary>A person's body radius for <see cref="Bodies"/>.</summary>
    private const float Body = 0.3f;

    /// <summary>A line people walk: world XZ points and the surface height
    /// at each (a road's own level, so ramps, stairs and bridges carry them).</summary>
    public sealed class Route
    {
        public Vector2[] P = Array.Empty<Vector2>();
        public float[] Y = Array.Empty<float>();
        /// <summary>Half the width they may walk in, either side of the line.</summary>
        public float Half = 1.5f;
    }

    private sealed class Kind
    {
        public string Name = "";
        public MultiMesh Face = null!, Shadow = null!;
        public ShaderMaterial Mat = null!;
        public Texture2D Low = null!, Top = null!;
        public QuadMesh LowQuad = null!, TopQuad = null!;
        public int Count;
        // every instance's 12 transform floats + 4 custom, written in place and
        // handed over whole once a frame: one call per MultiMesh, not four per
        // person (~200 people x 4 interop calls a frame otherwise)
        public float[] FaceBuf = Array.Empty<float>(), ShadowBuf = Array.Empty<float>();
        public bool Dirty;
    }

    private sealed class Person
    {
        public Kind K = null!;
        public int Slot;
        public Route? R;
        public int Seg, Step = 1;
        public float Lane;
        public Vector2 P, Home, Heading = new(0f, 1f);
        public float Y, Speed, Wait, Clock, Travel, Cycle, Talk, Held;
        public int Facing, Line;
        public bool Shown = true;
        /// <summary>sit, carry or work (the bake's extra actions); null walks and idles.
        /// Hold: keeps its facing (a vendor at the counter, a group round a talker), with
        /// a glance now and then, and no stroll -- the outside review read people turning
        /// at random as "game markers placed in the environment".</summary>
        public string? Act;
        public bool Hold;
        public Vector2 Face;
        public Label3D? Bubble;
    }

    private static readonly Dictionary<string, string[]> Lines = new()
    {
        ["farmer"] = new[] { "Rain's coming. My knee says so.", "The mill's turning well today.", "Fresh eggs at the market, if the hens behave.", "Mind the geese by the barn." },
        ["merchant"] = new[] { "Finest cloth this side of the river!", "Prices? Fair. Mostly.", "Mind the purse-cutters by the fountain.", "Ships from the south came in. Business is good." },
        ["guard"] = new[] { "Move along, citizen.", "Quiet at the gate, so far.", "The citadel's closed to visitors.", "No running on the wall stairs." },
        ["market_woman"] = new[] { "Apples! Two for a copper!", "You look hungry, love.", "The pigeons steal more than the thieves.", "Bread's fresh till noon." },
        ["noble_lady"] = new[] { "The view from the Noble Terrace is divine.", "Have you seen a little dog about?", "One simply doesn't walk the Lower City.", "The chapel bells are lovely at dusk." },
        ["old_man"] = new[] { "In my day the walls were taller.", "Sit a while. The fountain's pleasant.", "I've counted every stair to the citadel. Twice.", "The river ran the other way once. Or so I dreamt." },
        ["child"] = new[] { "Race you to the fountain!", "The black cat is lucky, I swear.", "My dog can sit. Watch!", "Have you been up on the wall? It's so high!" },
        ["blacksmith"] = new[] { "Hot work, this.", "Need a blade sharpened?", "That anvil's been in the family four generations.", "Smoke's thick today. Good fires." },
        ["monk"] = new[] { "Peace be with you, traveller.", "The chapel bell rings at dusk.", "Walk gently; the world is listening.", "Even the cats come to evening prayer." },
        ["fisher"] = new[] { "The herring are running thin this year.", "Mind the nets, friend.", "Salt in the air, salt in the blood.", "Storm out past the lighthouse, they say." },
        ["dockhand"] = new[] { "Heavy one, this.", "Mind your back -- crate coming through!", "Ship's in, and the foreman's shouting.", "A copper a crate. Honest work." },
        ["young_woman"] = new[] { "Lovely afternoon for the harbour.", "Have you tried the tavern's pie?", "The gulls take the fish right off the quay!", "Meet me by the fountain later?" },
    };

    private readonly Dictionary<string, Kind> _kinds = new();
    private readonly List<Person> _people = new();
    private readonly Bodies _bodies = new() { Solid = true };
    private Node3D _player = null!;
    private CameraRig _cam = null!;
    private Random _rng = new(1);
    private Basis _sun;
    private bool? _top;
    private Color _tint = new(-1f, 0f, 0f);
    private int _cols, _rows, _idleCol, _idleN, _walkCol, _walkN;
    private int _sitCol, _sitN, _carryCol, _carryN, _workCol, _workN;
    private float _tpm = 52f;
    private float _far;
    private static Shader? _shader;

    /// <summary>Every live one, for the capture harness.</summary>
    public static readonly List<Townsfolk> All = new();

    public int Count => _people.Count;
    public IEnumerable<Vector3> Positions { get { foreach (var p in _people) yield return new Vector3(p.P.X, p.Y, p.P.Y); } }

    public void Bind(Node3D player, CameraRig cam, int seed)
    {
        _player = player;
        _cam = cam;
        _rng = new Random(seed);
        _sun = Basis.FromEuler(new Vector3(0f, Mathf.DegToRad(Grade.L.Yaw + 180f), 0f));
        All.Add(this);
        Bodies.All.Add(_bodies);
        Interact.Add(Offer);
        var m = (Godot.Collections.Dictionary)Json.ParseString(FileAccess.GetFileAsString(Dir + "manifest.json"));
        var cell = (Godot.Collections.Array)m["cell_px"];
        var cw = (int)cell[0];
        var ch = (int)cell[1];
        _tpm = (float)m["tpm"];
        var acts = (Godot.Collections.Dictionary)m["actions"];
        var idle = (Godot.Collections.Dictionary)acts["idle"];
        var walk = (Godot.Collections.Dictionary)acts["walk"];
        (_idleCol, _idleN, _walkCol, _walkN) = ((int)idle["col"], (int)idle["frames"], (int)walk["col"], (int)walk["frames"]);
        (int, int) Opt(string a) => acts.ContainsKey(a)
            ? ((int)((Godot.Collections.Dictionary)acts[a])["col"], (int)((Godot.Collections.Dictionary)acts[a])["frames"]) : (0, 0);
        (_sitCol, _sitN) = Opt("sit");
        (_carryCol, _carryN) = Opt("carry");
        (_workCol, _workN) = Opt("work");
        // every column the sheet holds (the extra actions sit after walk)
        _cols = 0;
        foreach (var a in acts.Values)
        {
            var d = (Godot.Collections.Dictionary)a;
            _cols = Mathf.Max(_cols, (int)d["col"] + (int)d["frames"]);
        }
        _rows = ((Godot.Collections.Array)m["facings"]).Count;
        var degs = (Godot.Collections.Array)m["degs"];
        var lowKey = ((int)(float)degs[0]).ToString();
        var topKey = ((int)(float)degs[degs.Count - 1]).ToString();
        var feet = (Godot.Collections.Dictionary)m["foot_px"];
        QuadMesh Quad(string key)
        {
            var f = (Godot.Collections.Dictionary)feet[key];
            var s = 0f;
            foreach (var v in f.Values) s += (float)v;
            var foot = s / Mathf.Max(f.Count, 1) / _tpm;
            var size = new Vector2(cw / _tpm, ch / _tpm);
            return new QuadMesh { Size = size, CenterOffset = new Vector3(0f, size.Y / 2f - foot, 0f) };
        }
        var lowQuad = Quad(lowKey);
        var topQuad = Quad(topKey);
        _shader ??= new Shader { Code = Code };
        var files = (Godot.Collections.Dictionary)m["files"];
        foreach (var name in (Godot.Collections.Array)m["variants"])
        {
            var n = (string)name;
            var fs = (Godot.Collections.Dictionary)files[n];
            var k = new Kind
            {
                Name = n, LowQuad = lowQuad, TopQuad = topQuad,
                Low = Load((string)fs[lowKey]), Top = Load((string)fs[topKey]),
                Mat = new ShaderMaterial { Shader = _shader },
            };
            k.Mat.SetShaderParameter("grid", new Vector2(_cols, _rows));
            _kinds[n] = k;
        }
    }

    private static Texture2D Load(string file)
    {
        var img = Image.LoadFromFile(ProjectSettings.GlobalizePath(Dir + file));
        return ImageTexture.CreateFromImage(img);
    }

    public override void _ExitTree()
    {
        All.Remove(this);
        Bodies.All.Remove(_bodies);
        Interact.Remove(Offer);
    }

    private float U() => (float)_rng.NextDouble();

    private Person New(string kind)
    {
        // a kind the loaded sheet does not hold (a bake older than the code) walks as a farmer
        if (!_kinds.ContainsKey(kind)) kind = _kinds.ContainsKey("farmer") ? "farmer" : _kinds.Keys.First();
        var k = _kinds[kind];
        var p = new Person
        {
            K = k, Slot = k.Count++, Clock = U() * 10f, Line = _rng.Next(4),
            Speed = kind switch { "old_man" => 0.55f, "child" => 1.45f, "guard" => 1.05f, _ => 0.9f + U() * 0.4f },
            Cycle = kind switch { "old_man" => 0.85f, "child" => 1.0f, _ => 1.4f },
        };
        _people.Add(p);
        return p;
    }

    /// <summary>Someone walking `r` from a random point, in a random direction,
    /// keeping to one side of it.</summary>
    public void Walker(string kind, Route r)
    {
        if (Bake.Person(this, "walker", kind, r, default, 0f, null, null)) AddWalker(kind, r);
    }

    internal void AddWalker(string kind, Route r)
    {
        if (r.P.Length < 2) return;
        var p = New(kind);
        p.R = r;
        p.Seg = _rng.Next(r.P.Length - 1);
        p.Step = U() < 0.5f ? 1 : -1;
        if (p.Seg + p.Step < 0 || p.Seg + p.Step >= r.P.Length) p.Step = -p.Step;
        p.Lane = (0.25f + U() * 0.75f) * r.Half;
        p.P = r.P[p.Seg];
        p.Y = r.Y[p.Seg];
    }

    /// <summary>Someone standing about at `at` (height `y`), turning now and
    /// then, stepping a pace or two.</summary>
    /// <summary>Someone carrying a crate along `r` (back and forth between cargo).</summary>
    public void Carrier(string kind, Route r)
    {
        if (Bake.Person(this, "carrier", kind, r, default, 0f, null, null)) AddCarrier(kind, r);
    }

    internal void AddCarrier(string kind, Route r)
    {
        AddWalker(kind, r);
        var p = _people[^1];
        p.Act = "carry";
        p.Speed = 0.7f + U() * 0.15f;
    }

    /// <summary>A stander who keeps facing `face`: sitting, working, or held at a counter
    /// or in a group.</summary>
    public void Holder(string kind, Vector2 at, float y, Vector2 face, string? act = null)
    {
        if (Bake.Person(this, "holder", kind, null, at, y, face, act)) AddHolder(kind, at, y, face, act);
    }

    internal void AddHolder(string kind, Vector2 at, float y, Vector2 face, string? act = null)
    {
        AddStander(kind, at, y, face);
        var p = _people[^1];
        p.Act = act;
        p.Hold = true;
        p.Face = p.Heading;
    }

    public void Stander(string kind, Vector2 at, float y, Vector2? face = null)
    {
        if (Bake.Person(this, "stander", kind, null, at, y, face, null)) AddStander(kind, at, y, face);
    }

    internal void AddStander(string kind, Vector2 at, float y, Vector2? face = null)
    {
        // not on top of someone already standing there (random stall and
        // fountain spots can land within a body of each other)
        foreach (var o in _people)
            if (o.R == null) at = Bodies.Out(at, o.P, 2f * Body);
        var p = New(kind);
        p.P = p.Home = at;
        p.Y = y;
        if (face is { } f && (f - at).LengthSquared() > 1e-4f) p.Heading = (f - at).Normalized();
        p.Wait = U() * 6f;
    }

    /// <summary>Make the MultiMeshes once everyone is added.</summary>
    public void Finish()
    {
        Bake.People(this);   // a baked scene's people, before the batches are made
        foreach (var k in _kinds.Values)
        {
            if (k.Count == 0) continue;
            k.Face = Batch(k.Name, k, GeometryInstance3D.ShadowCastingSetting.Off);
            k.Shadow = Batch(k.Name + "_shadow", k, GeometryInstance3D.ShadowCastingSetting.ShadowsOnly);
            k.FaceBuf = new float[k.Count * 16];
            k.ShadowBuf = new float[k.Count * 16];
            k.Dirty = true;
        }
        GD.Print($"{Name}: {_people.Count} people");
    }

    private MultiMesh Batch(string name, Kind k, GeometryInstance3D.ShadowCastingSetting cast)
    {
        var mm = new MultiMesh
        {
            TransformFormat = MultiMesh.TransformFormatEnum.Transform3D,
            UseCustomData = true, Mesh = k.TopQuad, InstanceCount = k.Count,
        };
        AddChild(new MultiMeshInstance3D
        {
            Name = name, Multimesh = mm, MaterialOverride = k.Mat, CastShadow = cast,
            PhysicsInterpolationMode = PhysicsInterpolationModeEnum.Off,
        });
        return mm;
    }

    public override void _Process(double delta)
    {
        if (_player == null || _people.Count == 0) return;
        var dt = (float)delta;
        var top = _cam.TopSet;
        if (top != _top)
        {
            _top = top;
            foreach (var k in _kinds.Values)
            {
                k.Mat.SetShaderParameter("tex", top ? k.Top : k.Low);
                if (k.Count == 0) continue;
                k.Face.Mesh = top ? k.TopQuad : k.LowQuad;
                k.Shadow.Mesh = k.Face.Mesh;
            }
        }
        var mod = Grade.SpriteModulate();
        var keep = Weather.FigureKeep;
        var tint = new Color(mod.R * keep * (1f - 0.22f * Weather.Soak), mod.G * keep * (1f - 0.2f * Weather.Soak),
                             mod.B * keep * (1f - 0.14f * Weather.Soak));
        if (!tint.IsEqualApprox(_tint))
        {
            _tint = tint;
            foreach (var k in _kinds.Values) k.Mat.SetShaderParameter("tint", tint);
        }
        var face = Basis.FromEuler(new Vector3(-_cam.PitchRad, _cam.YawRad, 0f));
        var pl = _player.GetGlobalTransformInterpolated().Origin;
        var me = new Vector2(pl.X, pl.Z);
        // far away: stepped four times a second, drawn nowhere
        _far += dt;
        var farTick = _far >= 0.25f;
        if (farTick) _far = 0f;
        _bodies.Clear();
        for (var i = 0; i < _people.Count; i++) _bodies.Add(_people[i].P, Body, i);
        for (var i = 0; i < _people.Count; i++)
        {
            var p = _people[i];
            var near = (p.P - me).LengthSquared() < Near * Near;
            if (!near && !farTick && !p.Shown) continue;
            Move(p, i, me, near ? dt : 0.25f, near);
            Draw(p, face, near);
        }
        foreach (var k in _kinds.Values)
        {
            if (!k.Dirty) continue;
            k.Dirty = false;
            k.Face.Buffer = k.FaceBuf;
            k.Shadow.Buffer = k.ShadowBuf;
        }
    }

    private void Move(Person p, int i, Vector2 me, float dt, bool near)
    {
        p.Clock += dt;
        var toMe = me - p.P;
        var dist = toMe.Length();
        if (p.Talk > 0f)
        {
            p.Talk -= dt;
            if (dist > 0.1f) p.Heading = toMe / dist;
            if (p.Talk <= 0f || dist > 5f) Hush(p);
            return;
        }
        if (p.Wait > 0f)
        {
            p.Wait -= dt;
            return;
        }
        if (p.R == null && p.Hold)
        {
            // held: a glance aside now and then, back to the counter, the group, the work
            var g = U();
            p.Heading = g < 0.2f ? p.Face.Rotated(0.6f) : g < 0.4f ? p.Face.Rotated(-0.6f) : p.Face;
            p.Wait = 2f + U() * 5f;
            return;
        }
        if (p.R == null)
        {
            // standing about: turn to a new direction, or step a pace or two
            var t = U();
            if (t < 0.55f)
            {
                var a = U() * Mathf.Tau;
                p.Heading = new Vector2(Mathf.Cos(a), Mathf.Sin(a));
                p.Wait = 2f + U() * 6f;
            }
            else
            {
                var a = U() * Mathf.Tau;
                var goal = p.Home + new Vector2(Mathf.Cos(a), Mathf.Sin(a)) * U() * 1.6f;
                var d = goal - p.P;
                // not into anyone, the player included
                if (d.Length() > 0.2f && Bodies.Push(goal, Body, _bodies, i) == goal
                    && (goal - me).Length() > Body + Player.Radius + 0.3f)
                {
                    p.Heading = d.Normalized();
                    p.P = goal;   // a short stroll, taken at once; the frames below still walk
                    p.Travel += d.Length();
                }
                p.Wait = 1f + U() * 4f;
            }
            return;
        }
        var r = p.R;
        var next = p.Seg + p.Step;
        if (next < 0 || next >= r.P.Length)
        {
            p.Step = -p.Step;
            next = p.Seg + p.Step;
            p.Wait = 1f + U() * 3f;
        }
        Vector2 a0 = r.P[p.Seg], b0 = r.P[next];
        var seg = b0 - a0;
        var len = Mathf.Max(seg.Length(), 1e-3f);
        var u = seg / len;
        var side = new Vector2(-u.Y, u.X);
        var target = b0 + side * p.Lane;
        var to = target - p.P;
        var left = to.Length();
        if (left < 0.3f)
        {
            p.Seg = next;
            if (U() < 0.035f) p.Wait = 1.5f + U() * 4f;
            return;
        }
        // someone in the way -- the player, a person, an animal: stop and look
        // at them; after 2 s step round them on the side they are not on, and
        // after 8 s turn back, so two people cannot hold each other up for good
        var ahead = to / left;
        // ponytail: off screen (past Near) nobody collides -- no one sees it
        var block = dist < 1.4f && toMe.Dot(ahead) > 0f ? toMe : near ? Bodies.Ahead(p.P, ahead, 0.9f, Body, _bodies, i) : null;
        if (block is { } bv)
        {
            p.Held += dt;
            if (p.Held > 8f)
            {
                p.Seg = next;
                p.Step = -p.Step;
                p.Held = 0f;
                return;
            }
            if (p.Held < 2f)
            {
                p.Heading = bv.Normalized();
                return;
            }
            ahead = (ahead - side * (bv.Dot(side) >= 0f ? 1f : -1f)).Normalized();
        }
        else p.Held = 0f;
        var step = Mathf.Min(p.Speed * dt, left);
        p.Heading = ahead;
        // out of anyone brushed, and of the player, but never past the walkable
        // width: off a bridge deck or a ramp that is a drop
        var np = p.P + ahead * step;
        if (near) np = Bodies.Out(Bodies.Push(np, Body, _bodies, i), me, Body + Player.Radius);
        var lat = (np - a0).Dot(side);
        np -= side * (lat - Mathf.Clamp(lat, -r.Half, r.Half));
        p.Travel += (np - p.P).Length();
        p.P = np;
        var t0 = Mathf.Clamp((p.P - a0).Dot(u) / len, 0f, 1f);
        p.Y = Mathf.Lerp(r.Y[p.Seg], r.Y[next], t0);
    }

    private bool Moving(Person p) => p.Talk <= 0f && p.Wait <= 0f && p.R != null;

    private void Draw(Person p, Basis face, bool near)
    {
        if (!near)
        {
            if (!p.Shown) return;
            p.Shown = false;
            var zero = new Basis(Vector3.Zero, Vector3.Zero, Vector3.Zero);
            var o = new Vector3(p.P.X, p.Y, p.P.Y);
            Put(p.K.FaceBuf, p.Slot, zero, o, default);
            Put(p.K.ShadowBuf, p.Slot, zero, o, default);
            p.K.Dirty = true;
            return;
        }
        p.Shown = true;
        p.Facing = _cam.FacingFor(new Vector3(p.Heading.X, 0f, p.Heading.Y), p.Facing);
        var col = Moving(p)
            ? p.Act == "carry" && _carryN > 0 ? _carryCol + (int)(p.Travel / p.Cycle * _carryN) % _carryN
              : _walkCol + (int)(p.Travel / p.Cycle * _walkN) % _walkN
            : p.Act == "sit" && _sitN > 0 ? _sitCol + (int)(p.Clock * 0.8f) % _sitN
            : p.Act == "work" && _workN > 0 ? _workCol + (int)(p.Clock * 3.2f) % _workN
            : p.Act == "carry" && _carryN > 0 ? _carryCol
            : _idleCol + (int)(p.Clock * 3f) % _idleN;
        var at = new Vector3(p.P.X, p.Y, p.P.Y);
        var cell = new Color(col, p.Facing, 0f, 0f);
        Put(p.K.FaceBuf, p.Slot, face, at, cell);
        Put(p.K.ShadowBuf, p.Slot, _sun, at, cell);
        p.K.Dirty = true;
        if (p.Bubble != null) p.Bubble.Position = at + Vector3.Up * 2.35f;
    }

    /// <summary>MultiMesh buffer layout: the transform's three rows (basis
    /// row, origin component), then the custom data.</summary>
    internal static void Put(float[] buf, int slot, in Basis b, Vector3 o, Color c)
    {
        var i = slot * 16;
        buf[i] = b.X.X; buf[i + 1] = b.Y.X; buf[i + 2] = b.Z.X; buf[i + 3] = o.X;
        buf[i + 4] = b.X.Y; buf[i + 5] = b.Y.Y; buf[i + 6] = b.Z.Y; buf[i + 7] = o.Y;
        buf[i + 8] = b.X.Z; buf[i + 9] = b.Y.Z; buf[i + 10] = b.Z.Z; buf[i + 11] = o.Z;
        buf[i + 12] = c.R; buf[i + 13] = c.G; buf[i + 14] = c.B; buf[i + 15] = c.A;
    }

    private Interact.Offer? Offer(Vector2 me)
    {
        Person? best = null;
        var bd = 2.2f;
        foreach (var p in _people)
        {
            var d = (p.P - me).Length();
            if (d < bd) { bd = d; best = p; }
        }
        if (best == null) return null;
        var who = best;
        return new Interact.Offer(bd, "E: talk", () => TalkTo(who));
    }

    private void TalkTo(Person p)
    {
        var lines = Lines.TryGetValue(p.K.Name, out var l) ? l : new[] { "Good day." };
        var text = lines[p.Line++ % lines.Length];
        p.Talk = 4.5f;
        p.Wait = 0f;
        if (p.Bubble == null)
        {
            p.Bubble = new Label3D
            {
                Billboard = BaseMaterial3D.BillboardModeEnum.Enabled, NoDepthTest = true, FontSize = 30,
                OutlineSize = 10, PixelSize = 0.011f, Modulate = new Color(1f, 0.95f, 0.84f),
                OutlineModulate = new Color(0.1f, 0.08f, 0.07f), AutowrapMode = TextServer.AutowrapMode.WordSmart,
                Width = 420f, RenderPriority = 10,
            };
            AddChild(p.Bubble);
        }
        p.Bubble.Text = text;
        p.Bubble.Position = new Vector3(p.P.X, p.Y + 2.35f, p.P.Y);
    }

    private static void Hush(Person p)
    {
        p.Talk = 0f;
        p.Bubble?.QueueFree();
        p.Bubble = null;
    }

    /// <summary>A heart that floats up and fades: an animal liked being petted.</summary>
    public static void Heart(Node parent, Vector3 at)
    {
        Hearts++;
        _heart ??= HeartTexture();
        var s = new Sprite3D
        {
            Texture = _heart, PixelSize = 0.055f, Billboard = BaseMaterial3D.BillboardModeEnum.Enabled,
            TextureFilter = BaseMaterial3D.TextureFilterEnum.Nearest, Shaded = false, NoDepthTest = true,
            AlphaCut = SpriteBase3D.AlphaCutMode.Discard, RenderPriority = 10,
        };
        parent.AddChild(s);
        s.GlobalPosition = at;
        var tw = s.CreateTween();
        tw.SetParallel();
        tw.TweenProperty(s, "global_position", at + Vector3.Up * 0.9f, 1.8f);
        tw.TweenProperty(s, "modulate:a", 0f, 0.8f).SetDelay(1.0f);
        tw.Chain().TweenCallback(Callable.From(s.QueueFree));
    }

    private static Texture2D? _heart;
    /// <summary>Hearts shown so far, for the capture harness.</summary>
    public static int Hearts;

    /// <summary>Pairs of people standing closer than `d`, among those within
    /// <see cref="Near"/> of `around` (past it nobody collides), for the harness.</summary>
    public int Overlaps(float d, Vector2 around)
    {
        var n = 0;
        for (var i = 0; i < _people.Count; i++)
        {
            if ((_people[i].P - around).LengthSquared() > Near * Near) continue;
            for (var j = i + 1; j < _people.Count; j++)
                if ((_people[j].P - around).LengthSquared() <= Near * Near
                    && (_people[i].P - _people[j].P).LengthSquared() < d * d) n++;
        }
        return n;
    }

    /// <summary>The nearest person to `at` (2D), for the harness.</summary>
    public float Nearest(Vector2 at)
    {
        var best = float.MaxValue;
        foreach (var p in _people) best = Mathf.Min(best, (p.P - at).Length());
        return best;
    }

    private static Texture2D HeartTexture()
    {
        string[] rows =
        {
            ".XX...XX.", "XooX.XooX", "XoooXoooX", "XoooooooX", ".XoooooX.", "..XoooX..", "...XoX...", "....X....",
        };
        var img = Image.CreateEmpty(9, 8, false, Image.Format.Rgba8);
        for (var y = 0; y < rows.Length; y++)
        for (var x = 0; x < 9; x++)
            img.SetPixel(x, y, rows[y][x] switch
            {
                'X' => new Color(0.35f, 0.05f, 0.08f),
                'o' => new Color(0.93f, 0.25f, 0.33f),
                _ => new Color(0f, 0f, 0f, 0f),
            });
        return ImageTexture.CreateFromImage(img);
    }

    private const string Code = @"
shader_type spatial;
render_mode unshaded, cull_disabled, shadows_disabled;

uniform sampler2D tex : source_color, filter_nearest;
uniform vec2 grid;
// the player's colour multiplier (Grade.SpriteModulate x Weather.FigureKeep):
// unshaded, so the region's exposure is divided back out
uniform vec3 tint : source_color = vec3(1.0);
varying flat vec2 cell;

void vertex() {
    cell = INSTANCE_CUSTOM.xy;
}

void fragment() {
    vec4 c = texture(tex, (cell + UV) / grid);
    ALBEDO = c.rgb * tint;
    ALPHA = c.a;
    ALPHA_SCISSOR_THRESHOLD = 0.5;
}
";
}

/// <summary>
/// One E key for everything the player can use (user, 2026-09-26:
/// "animals and shit that are intractable"): people to talk to, animals to
/// pet. Each system offers its nearest thing; the closest offer wins, shows
/// its hint on the weather line (where the boat's "E: board" goes) and runs
/// on E.
/// </summary>
public static class Interact
{
    public readonly record struct Offer(float Dist, string Hint, Action Act);

    private static readonly List<Func<Vector2, Offer?>> _from = new();

    public static void Add(Func<Vector2, Offer?> f) => _from.Add(f);
    public static void Remove(Func<Vector2, Offer?> f) => _from.Remove(f);

    public static Offer? Best(Vector2 me)
    {
        Offer? best = null;
        foreach (var f in _from)
            if (f(me) is { } o && (best == null || o.Dist < best.Value.Dist)) best = o;
        return best;
    }
}

/// <summary>
/// People and land animals as circles, so they stop passing through each
/// other and the player (user, 2026-09-26: "do all these", of "people and
/// animals pass through you and each other"). Each Townsfolk and Fauna owns
/// one and refills it at the top of its `_Process`; a query looks through all
/// of them, so another system's bodies are at most a frame old. People are
/// Solid: the player is pushed out of them. Animals are not: the player
/// shoves them aside instead (a dog sat in an alley would wall it off).
/// </summary>
public sealed class Bodies
{
    public static readonly List<Bodies> All = new();
    /// <summary>Grid cell (m). A query scans only the cells its reach touches
    /// (the asker's radius plus this system's largest body, or the look-ahead):
    /// 1-4 of them. Scanning a fixed 3x3 cost ~1.3 ms a frame with folk on
    /// (2026-09-27 `--folkprice`: frame mean 8.04 against 6.58 with them off).</summary>
    private const float Cell = 2f;
    private float _maxR;
    public bool Solid;
    private readonly Dictionary<Vector2I, List<Vector4>> _cells = new();
    private readonly List<List<Vector4>> _used = new();
    // bounds of this frame's bodies: a query in another town skips the lot
    private Vector2 _lo = new(float.MaxValue, float.MaxValue), _hi = new(float.MinValue, float.MinValue);

    public void Clear()
    {
        foreach (var l in _used) l.Clear();
        _used.Clear();
        _lo = new Vector2(float.MaxValue, float.MaxValue);
        _hi = new Vector2(float.MinValue, float.MinValue);
        _maxR = 0f;
    }

    public void Add(Vector2 p, float r, int id)
    {
        var k = Key(p);
        if (!_cells.TryGetValue(k, out var l)) _cells[k] = l = new List<Vector4>();
        if (l.Count == 0) _used.Add(l);
        l.Add(new Vector4(p.X, p.Y, r, id));
        _lo = new Vector2(Mathf.Min(_lo.X, p.X), Mathf.Min(_lo.Y, p.Y));
        _hi = new Vector2(Mathf.Max(_hi.X, p.X), Mathf.Max(_hi.Y, p.Y));
        _maxR = Mathf.Max(_maxR, r);
    }

    private static Vector2I Key(Vector2 p) => new(Mathf.FloorToInt(p.X / Cell), Mathf.FloorToInt(p.Y / Cell));

    private bool Far(Vector2 p) =>
        p.X < _lo.X - Cell || p.Y < _lo.Y - Cell || p.X > _hi.X + Cell || p.Y > _hi.Y + Cell;

    /// <summary>`p` (radius `r`) moved out of every body but `self`'s number
    /// `id`; `solid`: people only.</summary>
    public static Vector2 Push(Vector2 p, float r, Bodies? self, int id, bool solid = false)
    {
        foreach (var b in All)
        {
            if ((solid && !b.Solid) || b.Far(p)) continue;
            var reach = new Vector2(r + b._maxR, r + b._maxR);
            Vector2I lo = Key(p - reach), hi = Key(p + reach);
            for (var i = lo.X; i <= hi.X; i++)
            for (var j = lo.Y; j <= hi.Y; j++)
            {
                if (!b._cells.TryGetValue(new Vector2I(i, j), out var l)) continue;
                foreach (var o in l)
                    if (b != self || (int)o.W != id) p = Out(p, new Vector2(o.X, o.Y), r + o.Z);
            }
        }
        return p;
    }

    /// <summary>`p` moved to at least `min` from `c`.</summary>
    public static Vector2 Out(Vector2 p, Vector2 c, float min)
    {
        var d = p - c;
        var l2 = d.LengthSquared();
        if (l2 >= min * min) return p;
        return c + (l2 > 1e-8f ? d / Mathf.Sqrt(l2) : Vector2.Right) * min;
    }

    /// <summary>The nearest body in the way of someone (radius `r`) at `p`
    /// heading `dir`: within `reach` ahead, overlapping their path. Its offset
    /// from `p`, or null.</summary>
    public static Vector2? Ahead(Vector2 p, Vector2 dir, float reach, float r, Bodies self, int id)
    {
        Vector2? best = null;
        var bd = reach;
        // a body counts if its centre is < reach ahead and < r + its radius aside
        var box = new Vector2(reach, reach);
        Vector2I lo = Key(p - box), hi = Key(p + box);
        foreach (var b in All)
        {
            if (b.Far(p)) continue;
            for (var i = lo.X; i <= hi.X; i++)
            for (var j = lo.Y; j <= hi.Y; j++)
            {
                if (!b._cells.TryGetValue(new Vector2I(i, j), out var l)) continue;
                foreach (var o in l)
                {
                    if (b == self && (int)o.W == id) continue;
                    var d = new Vector2(o.X, o.Y) - p;
                    var along = d.Dot(dir);
                    if (along <= 0f || along >= bd || Mathf.Abs(d.Cross(dir)) > r + o.Z) continue;
                    bd = along;
                    best = d;
                }
            }
        }
        return best;
    }
}

/// <summary>Polls <see cref="Interact"/> for the player each frame.</summary>
public partial class Interactor : Node
{
    private Node3D _player = null!;
    private bool _ePrev, _hinted;

    public void Bind(Node3D player) => _player = player;

    public override void _Process(double delta)
    {
        if (_player == null) return;
        if (Boat.Aboard) return;
        var p = _player.GlobalPosition;
        var best = Interact.Best(new Vector2(p.X, p.Z));
        if (best is { } o)
        {
            Weather.Hint = o.Hint;
            _hinted = true;
        }
        else if (_hinted)
        {
            Weather.Hint = "";
            _hinted = false;
        }
        var e = Input.IsPhysicalKeyPressed(Key.E);
        if (e && !_ePrev && best is { } b) b.Act();
        _ePrev = e;
    }
}
