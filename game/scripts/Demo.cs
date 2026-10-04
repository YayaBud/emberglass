using System.Collections.Generic;
using Godot;

namespace Worldbuilder;

/// <summary>
/// A scripted run through every movement state, capturing one frame of each.
///
///     Godot.exe --path . -- --demo
///
/// This exists because the movement cannot be verified any other way from a
/// headless run: the state machine reads the keyboard, and a headless process
/// has no keyboard. It drives <see cref="Player.Drive"/> instead, holds each
/// state long enough to be in the middle of it rather than entering it, and
/// writes `shot_&lt;state&gt;.png` so `measure.py` has frames to measure and the
/// poses can be looked at side by side.
///
/// It is a verification harness, not a cutscene: the timings are chosen to land
/// mid-action, and anything that has to be seen moving still has to be played.
/// </summary>
public partial class Demo : Node
{
    private record Beat(string Name, float Hold, Vector3 Wish,
                        bool Jump = false, bool Dash = false,
                        bool Attack = false, bool Down = false,
                        bool Shoot = true);

    private static readonly Vector3 Fwd = new(-0.7071f, 0f, -0.7071f);   // screen "up"
    private static readonly Vector3 Right = new(0.7071f, 0f, -0.7071f);

    private readonly List<Beat> _beats = new()
    {
        new("settle",  1.2f, Vector3.Zero, Shoot: false),
        new("idle",    0.6f, Vector3.Zero),
        new("walk",    1.0f, Right),
        // Run is Shift, and Shift is also the dash -- so the run beat comes
        // after a dash has put the dash on cooldown, which is the same rule the
        // player experiences.
        new("dash",    0.12f, Right, Dash: true),
        new("run",     1.2f, Right, Dash: true),
        // Jump: pressed on the first tick of the beat, captured while rising.
        new("jump",    0.22f, Right, Jump: true),
        new("fall",    0.55f, Right),
        new("land",    0.9f, Vector3.Zero, Shoot: false),
        new("dash_end", 0.7f, Vector3.Zero, Shoot: false),
        new("attack",  0.18f, Fwd, Attack: true),
        // A beat with the button RELEASED. Drive only buffers an attack on the
        // rising edge, same as a real key press, so two attack beats back to
        // back are one press and the chain never fires.
        new("release", 0.05f, Fwd, Shoot: false),
        new("attack2", 0.30f, Fwd, Attack: true),
        new("recover", 0.9f, Vector3.Zero, Shoot: false),
        new("airdash", 0.30f, Right, Jump: true, Shoot: false),
        new("airdash2", 0.14f, Right, Dash: true),
        new("land2",   0.8f, Vector3.Zero, Shoot: false),
        // The dive needs air under it: jump, release, then down+attack. Captured
        // early in the beat, because a dive at 18 m/s is on the ground fast.
        new("jump2",   0.34f, Vector3.Zero, Jump: true, Shoot: false),
        new("dive",    0.26f, Vector3.Zero, Attack: true, Down: true),
        new("done",    0.6f, Vector3.Zero, Shoot: false),
    };

    private Player _player = null!;
    private int _beat;
    private float _t;
    private bool _shot;
    private readonly List<string> _written = new();

    public void Begin(Player player) => _player = player;

    // ---- the hybrid-camera walk: out of the outskirts and back ------------
    // Captures are triggered by the CAMERA's state, not by a clock: the point
    // is to show low, mid-blend and top-down, and a timeline would have to
    // guess how long walking to the zone edge takes.
    private CameraRig? _cam;
    private int _phase;
    private float _pt;

    public void BeginHybrid(Player player, CameraRig cam)
    {
        _player = player;
        _cam = cam;
    }

    private void Hybrid(float dt)
    {
        var cam = _cam!;
        _pt += dt;
        switch (_phase)
        {
            case 0:  // settled in the outskirts: low camera
                _player.Drive(Vector3.Zero, false, false, false, false);
                if (_pt > 1.6f) { Shoot("hyb_1_low"); Next(); }
                break;
            case 1:  // walk out, screen-right, until the camera is half way
                _player.Drive(Right, false, false, false, false);
                if (cam.Blend >= 0.5f) { Shoot("hyb_2_blend"); Next(); }
                break;
            case 2:  // fully top-down, then stop and let it settle
                _player.Drive(cam.Blend >= 0.999f ? Vector3.Zero : Right, false, false, false, false);
                if (cam.Blend >= 0.999f && _pt > 1.6f) { Shoot("hyb_3_top"); Next(); }
                break;
            case 3:  // walk back in
                _player.Drive(-Right, false, false, false, false);
                if (cam.Blend <= 0.001f) Next();
                break;
            case 4:  // back in the outskirts: low again
                _player.Drive(Vector3.Zero, false, false, false, false);
                if (_pt > 1.2f) { Shoot("hyb_4_back_low"); Next(); }
                break;
            default:
                GD.Print("demo: wrote " + string.Join(", ", _written));
                GetTree().Quit();
                return;
        }
        if (_pt > 15f)
        {
            GD.Print($"demo: TIMEOUT in phase {_phase}, blend {cam.Blend:F2}");
            GetTree().Quit();
        }
    }

    private void Next() { _phase++; _pt = 0f; }

    private void Shoot(string name)
    {
        var path = $"res://shot_{name}.png";
        GetViewport().GetTexture().GetImage().SavePng(path);
        _written.Add(name);
        GD.Print($"demo: {name,-15} blend={_cam!.Blend:F2} yaw={Mathf.RadToDeg(_cam.YawRad):F1}  {_player.Report()}");
    }

    public override void _Process(double delta)
    {
        if (_cam != null)
        {
            if (_player != null) Hybrid((float)delta);
            return;
        }
        if (_player == null || _beat >= _beats.Count) return;

        var b = _beats[_beat];
        _player.Drive(b.Wish, b.Jump, b.Dash, b.Attack, b.Down);
        _t += (float)delta;

        // Capture at 60 percent of the beat: far enough in to be mid-action,
        // not so far that a short action has already recovered.
        if (!_shot && b.Shoot && _t > b.Hold * (b.Name == "dive" ? 0.35f : 0.6f))
        {
            _shot = true;
            var path = $"res://shot_{b.Name}.png";
            var img = GetViewport().GetTexture().GetImage();
            img.SavePng(path);
            _written.Add(b.Name);
            GD.Print($"demo: {b.Name,-9} -> {path}  {_player.Report()}");
        }

        if (_t < b.Hold) return;
        _t = 0f;
        _shot = false;
        _beat++;
        if (_beat < _beats.Count) return;

        GD.Print("demo: wrote " + string.Join(", ", _written));
        GetTree().Quit();
    }
}
