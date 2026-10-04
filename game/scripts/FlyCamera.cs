using Godot;

namespace Worldbuilder;

/// <summary>
/// A free camera for surveying the world: mouse to look, WASD to move, Q and E
/// for down and up, Shift to go faster.
///
/// It reads physical keys directly rather than named input actions, so the
/// project needs no InputMap and a fresh clone runs with no setup. Swap this
/// for a real controller when there is something to control.
///
/// Click the window to take the mouse, Escape to give it back.
/// </summary>
public partial class FlyCamera : Camera3D
{
    [Export] public float Speed { get; set; } = 28f;
    [Export] public float SprintMultiplier { get; set; } = 5f;
    [Export] public float Sensitivity { get; set; } = 0.0026f;

    private float _yaw;
    private float _pitch;

    public override void _Ready()
    {
        _yaw = Rotation.Y;
        _pitch = Rotation.X;
        Current = true;
    }

    public override void _UnhandledInput(InputEvent e)
    {
        if (e is InputEventMouseButton { Pressed: true })
        {
            Input.MouseMode = Input.MouseModeEnum.Captured;
            return;
        }

        if (e is InputEventKey { Pressed: true, PhysicalKeycode: Key.Escape })
        {
            Input.MouseMode = Input.MouseModeEnum.Visible;
            return;
        }

        if (e is InputEventMouseMotion m
            && Input.MouseMode == Input.MouseModeEnum.Captured)
        {
            _yaw -= m.Relative.X * Sensitivity;
            // Clamped just short of straight up and straight down. At exactly
            // +/- 90 degrees the yaw axis and the view axis line up and the
            // camera rolls.
            _pitch = Mathf.Clamp(_pitch - m.Relative.Y * Sensitivity,
                                 -1.55f, 1.55f);
            Rotation = new Vector3(_pitch, _yaw, 0f);
        }
    }

    public override void _Process(double delta)
    {
        var dir = Vector3.Zero;
        if (Input.IsPhysicalKeyPressed(Key.W)) dir -= Basis.Z;
        if (Input.IsPhysicalKeyPressed(Key.S)) dir += Basis.Z;
        if (Input.IsPhysicalKeyPressed(Key.A)) dir -= Basis.X;
        if (Input.IsPhysicalKeyPressed(Key.D)) dir += Basis.X;
        if (Input.IsPhysicalKeyPressed(Key.E)) dir += Vector3.Up;
        if (Input.IsPhysicalKeyPressed(Key.Q)) dir -= Vector3.Up;

        if (dir == Vector3.Zero) return;

        var speed = Speed;
        if (Input.IsPhysicalKeyPressed(Key.Shift)) speed *= SprintMultiplier;
        Position += dir.Normalized() * speed * (float)delta;
    }
}
