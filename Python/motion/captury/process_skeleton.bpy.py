from __future__ import annotations

import sys
from pathlib import Path

import bpy


def main() -> None:
    if "--" not in sys.argv:
        raise SystemExit("Usage: blender --background --python process.py -- <input.fbx>")

    args = sys.argv[sys.argv.index("--") + 1:]

    if len(args) != 1:
        raise SystemExit("Usage: blender --background --python process.py -- <input.fbx>")

    input_path = Path(args[0]).expanduser().resolve()
    output_path = input_path.with_name(f"{input_path.stem}_processed.fbx")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    bpy.ops.import_scene.fbx(filepath=str(input_path))

    armatures = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "ARMATURE"
    ]

    for armature in armatures:
        for bone in armature.data.bones:
            name = bone.name.split(":", 1)[-1].lower()
            bone.name = name

    bpy.ops.object.select_all(action="SELECT")

    result = bpy.ops.export_scene.fbx(
        filepath=str(output_path),
        use_selection=True,
        path_mode="AUTO",
        bake_anim=True,
        add_leaf_bones=False,
    )

    if "FINISHED" not in result:
        raise RuntimeError(f"FBX export failed: {result}")

    print(f"Exported: {output_path}")


if __name__ == "__main__":
    main()