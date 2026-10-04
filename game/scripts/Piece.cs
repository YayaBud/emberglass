using Godot;

namespace Worldbuilder;

/// <summary>
/// One asset in an editable scene (implementation_plan "Everything editable"): the
/// prefabs in `res://prefabs/&lt;kit&gt;/&lt;kind&gt;.tscn`, the asset sheet, and the baked
/// sites. Its data is only <see cref="Kit"/>, <see cref="Kind"/> and its transform.
/// In the tree (the editor, or the sheet run with F6) it shows the asset's in-game look
/// from `_vis/&lt;kind&gt;.scn` (written by <see cref="Bake"/>) as a child with no owner, so it
/// is never saved into the scene. The game reads a baked site without adding it to the
/// tree, so it takes the data and never loads the visual.
/// </summary>
[Tool, GlobalClass]
public partial class Piece : Node3D
{
    [Export] public string Kit { get; set; } = "";
    [Export] public string Kind { get; set; } = "";

    public override void _Ready()
    {
        if (Kind == "" || HasNode("_vis")) return;
        if (!Engine.IsEditorHint())
            for (var p = GetParent(); p != null; p = p.GetParent())
                if (p is World) return;   // world.tscn in the game: World reads it and frees it
        var path = $"res://prefabs/{Kit}/_vis/{Kind}.scn";
        if (!ResourceLoader.Exists(path)) return;
        var vis = GD.Load<PackedScene>(path).Instantiate();
        vis.Name = "_vis";
        AddChild(vis);
    }
}
