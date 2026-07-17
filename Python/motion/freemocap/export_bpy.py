from __future__ import annotations

import sys
from pathlib import Path

import bpy


def get_arguments() -> list[str]:
    if "--" not in sys.argv:
        return []

    return sys.argv[sys.argv.index("--") + 1 :]


def main() -> None:
    arguments = get_arguments()

    if len(arguments) != 1:
        raise SystemExit(
            "Usage: blender <file.blend> --background "
            "--python export_bpy.py -- <output.fbx>"
        )

    export_path = Path(arguments[0]).expanduser().resolve()
    export_path.parent.mkdir(parents=True, exist_ok=True)

    scene = bpy.context.scene

    armature = next(
        (
            obj
            for obj in scene.objects
            if obj.type == "ARMATURE"
        ),
        None,
    )

    if armature is None:
        raise RuntimeError("No armature found in the current Blender file.")

    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    animation_data = armature.animation_data
    active_action = animation_data.action if animation_data else None

    nla_strips = []
    if animation_data is not None:
        nla_strips = [
            strip
            for track in animation_data.nla_tracks
            for strip in track.strips
            if not track.mute and not strip.mute
        ]

    if active_action is None and not nla_strips:
        print(
            "WARNING: The armature has no active action or active NLA strips. "
            "Animation may instead be generated through constraints, drivers, "
            "or animated parent objects."
        )
    else:
        if active_action is not None:
            print(f"Active action: {active_action.name}")
            print(
                f"Action range: "
                f"{active_action.frame_range[0]} - "
                f"{active_action.frame_range[1]}"
            )

        print(f"Active NLA strips: {len(nla_strips)}")

    frame_start = int(scene.frame_start)
    frame_end = int(scene.frame_end)

    if frame_end < frame_start:
        raise RuntimeError(
            f"Invalid scene frame range: {frame_start} - {frame_end}"
        )

    print(f"Export frame range: {frame_start} - {frame_end}")

    # Force evaluation at the beginning of the exported range.
    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    armature.hide_set(False)
    armature.hide_viewport = False
    armature.hide_render = False
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    result = bpy.ops.export_scene.fbx(
        filepath=str(export_path),
        use_selection=True,
        object_types={"ARMATURE"},

        # Armature settings
        add_leaf_bones=True,

        # Bake the evaluated armature pose over the scene range.
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        bake_anim_force_startend_keying=True,
        bake_anim_step=1.0,
        bake_anim_simplify_factor=0.0,
    )

    if "FINISHED" not in result:
        raise RuntimeError(f"FBX export failed: {result}")

    if not export_path.is_file():
        raise RuntimeError(
            f"FBX exporter reported success, but no file was created: "
            f"{export_path}"
        )

    print(f"Exported animated FBX: {export_path}")


if __name__ == "__main__":
    main()