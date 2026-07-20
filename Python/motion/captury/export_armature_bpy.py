from __future__ import annotations

import sys
import math
from pathlib import Path

import bpy
from mathutils import Matrix

sys.path.append(r"C:\Users\Henry\AppData\Local\Programs\Python\Python313\Lib\site-packages")
from tqdm import tqdm 


NEW_ROOT_BONE_NAME = "Root"
NEW_ROOT_BONE_LENGTH = 0.1


def get_arguments() -> list[str]:
    if "--" not in sys.argv:
        return []

    return sys.argv[sys.argv.index("--") + 1 :]


def clear_scene() -> None:
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)

    for datablocks in (
        bpy.data.armatures,
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.actions,
    ):
        for datablock in list(datablocks):
            if datablock.users == 0:
                datablocks.remove(datablock)


def add_root_bone(armature: bpy.types.Object) -> tuple[str, list[str]]:
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")

    armature.hide_set(False)
    armature.hide_viewport = False
    armature.hide_render = False
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    bpy.ops.object.mode_set(mode="EDIT")

    edit_bones = armature.data.edit_bones

    spine_bone = next(
        (
            bone
            for bone in edit_bones
            if "spine" in bone.name.casefold()
        ),
        None,
    )

    if spine_bone is None:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise RuntimeError(
            f'No bone containing "spine" was found in armature: '
            f"{armature.name}"
        )

    original_root_bones = [
        bone
        for bone in edit_bones
        if bone.parent is None
    ]

    if not original_root_bones:
        bpy.ops.object.mode_set(mode="OBJECT")
        raise RuntimeError(
            f"No root bones were found in armature: {armature.name}"
        )

    new_root = edit_bones.new(NEW_ROOT_BONE_NAME)
    new_root.head = spine_bone.head.copy()
    new_root.tail = spine_bone.head.copy()
    new_root.tail.y -= NEW_ROOT_BONE_LENGTH

    # The new bone itself has no parent, making it the sole root bone.
    new_root.parent = None
    new_root.use_connect = False

    # Parent every previous root to the new bone without moving or connecting it.
    for root_bone in original_root_bones:
        root_bone.parent = new_root
        root_bone.use_connect = False

    created_name = new_root.name
    original_root_names = [bone.name for bone in original_root_bones]

    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    remaining_roots = [
        bone.name
        for bone in armature.data.bones
        if bone.parent is None
    ]

    if remaining_roots != [created_name]:
        raise RuntimeError(
            f"Expected {created_name!r} to be the sole root bone, "
            f"but found roots: {remaining_roots}"
        )

    print(
        f"Created root bone {created_name!r} at the head of "
        f"{spine_bone.name!r}"
    )
    print(
        "Reparented previous root bones: "
        + ", ".join(original_root_names)
    )

    return created_name, original_root_names


def set_scene_to_animation_range(
    scene: bpy.types.Scene,
    active_action: bpy.types.Action | None,
    nla_strips: list,
) -> tuple[int, int]:
    ranges: list[tuple[float, float]] = []

    if active_action is not None:
        ranges.append(tuple(active_action.frame_range))

    ranges.extend((strip.frame_start, strip.frame_end) for strip in nla_strips)

    if ranges:
        scene.frame_start = math.floor(min(start for start, _ in ranges))
        scene.frame_end = math.ceil(max(end for _, end in ranges))

    return int(scene.frame_start), int(scene.frame_end)


def keyframe_pose_transform(pose_bone: bpy.types.PoseBone, frame: int) -> None:
    pose_bone.keyframe_insert(data_path="location", frame=frame)

    if pose_bone.rotation_mode == "QUATERNION":
        pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
    elif pose_bone.rotation_mode == "AXIS_ANGLE":
        pose_bone.keyframe_insert(data_path="rotation_axis_angle", frame=frame)
    else:
        pose_bone.keyframe_insert(data_path="rotation_euler", frame=frame)

    pose_bone.keyframe_insert(data_path="scale", frame=frame)


def is_object_transform_curve(fcurve: bpy.types.FCurve) -> bool:
    return fcurve.data_path in {
        "location",
        "rotation_euler",
        "rotation_quaternion",
        "rotation_axis_angle",
        "scale",
        "delta_location",
        "delta_rotation_euler",
        "delta_rotation_quaternion",
        "delta_scale",
    }


def clear_object_transform_animation(armature: bpy.types.Object) -> None:
    animation_data = armature.animation_data
    if animation_data is None:
        return

    actions = []
    if animation_data.action is not None:
        actions.append(animation_data.action)

    actions.extend(
        strip.action
        for track in animation_data.nla_tracks
        for strip in track.strips
        if strip.action is not None
    )

    seen = set()
    removed = 0
    for action in actions:
        if action.as_pointer() in seen:
            continue
        seen.add(action.as_pointer())

        # Blender 4.4+ layered actions store F-curves inside channelbags.
        if hasattr(action, "layers") and len(action.layers) > 0:
            for layer in action.layers:
                for strip in layer.strips:
                    if strip.type != "KEYFRAME":
                        continue

                    for channelbag in strip.channelbags:
                        for fcurve in list(channelbag.fcurves):
                            if is_object_transform_curve(fcurve):
                                channelbag.fcurves.remove(fcurve)
                                removed += 1

        # Compatibility with legacy actions used by older Blender versions.
        elif hasattr(action, "fcurves"):
            for fcurve in list(action.fcurves):
                if is_object_transform_curve(fcurve):
                    action.fcurves.remove(fcurve)
                    removed += 1

    print(f"Removed {removed} object-level transform F-curves.")


def animate_root_from_object_motion(
    scene: bpy.types.Scene,
    armature: bpy.types.Object,
    root_name: str,
    child_names: list[str],
    original_object_matrices: dict[int, Matrix],
    original_child_world_matrices: dict[int, dict[str, Matrix]],
    base_object_matrix: Matrix,
    frame_start: int,
    frame_end: int,
) -> None:
    clear_object_transform_animation(armature)
    armature.matrix_world = base_object_matrix.copy()
    bpy.context.view_layer.update()

    root = armature.pose.bones[root_name]
    root_rest_matrix = root.bone.matrix_local.copy()

    print("Baking object motion into root bone")
    for frame in tqdm(range(frame_start, frame_end + 1)):
        scene.frame_set(frame)
        armature.matrix_world = base_object_matrix.copy()

        object_delta = (
            base_object_matrix.inverted_safe()
            @ original_object_matrices[frame]
        )
        root.matrix = object_delta @ root_rest_matrix
        keyframe_pose_transform(root, frame)

    bpy.context.view_layer.update()

    tolerance = 1.0e-4
    needs_child_offset = False
    print("Checking inherited child motion")
    for frame in tqdm(range(frame_start, frame_end + 1)):
        scene.frame_set(frame)
        armature.matrix_world = base_object_matrix.copy()
        bpy.context.view_layer.update()

        if any(
            max(
                abs(a - b)
                for row_a, row_b in zip(
                    armature.matrix_world @ armature.pose.bones[name].matrix,
                    original_child_world_matrices[frame][name],
                )
                for a, b in zip(row_a, row_b)
            )
            > tolerance
            for name in child_names
        ):
            needs_child_offset = True
            break

    if needs_child_offset:
        print("Offsetting immediate children to preserve original world motion")
        inverse_base = base_object_matrix.inverted_safe()
        for frame in tqdm(range(frame_start, frame_end + 1)):
            scene.frame_set(frame)
            armature.matrix_world = base_object_matrix.copy()
            bpy.context.view_layer.update()

            for name in child_names:
                child = armature.pose.bones[name]
                child.matrix = (
                    inverse_base
                    @ original_child_world_matrices[frame][name]
                )
                keyframe_pose_transform(child, frame)

        print("Offset immediate child animation to prevent double motion.")
    else:
        print("No child animation offset was necessary.")

    armature.matrix_world = base_object_matrix.copy()


def normalize_bone_names(armature: bpy.types.Object) -> None:
    for bone in armature.data.bones:
        name = bone.name

        if ":" in name:
            name = name.split(":", 1)[1]

        bone.name = name.lower()

def main() -> None:
    arguments = get_arguments()

    if len(arguments) != 2:
        raise SystemExit(
            "Usage: blender --background --python export_armature_bpy.py "
            "-- <input.fbx> <output.fbx>"
        )

    input_fbx = Path(arguments[0]).expanduser().resolve()
    output_fbx = Path(arguments[1]).expanduser().resolve()

    if not input_fbx.is_file():
        raise FileNotFoundError(f"Input FBX not found: {input_fbx}")

    output_fbx.parent.mkdir(parents=True, exist_ok=True)

    clear_scene()

    result = bpy.ops.import_scene.fbx(filepath=str(input_fbx))
    if "FINISHED" not in result:
        raise RuntimeError(f"FBX import failed: {result}")

    scene = bpy.context.scene

    imported_armatures = [
        obj
        for obj in scene.objects
        if obj.type == "ARMATURE"
    ]

    if not imported_armatures:
        raise RuntimeError(
            f"No armature was found in imported FBX: {input_fbx}"
        )

    if len(imported_armatures) > 1:
        print(
            f"WARNING: Found {len(imported_armatures)} armatures. "
            f"Using: {imported_armatures[0].name}"
        )

    armature = imported_armatures[0]

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
            "WARNING: The imported armature has no active action or active "
            "NLA strips. The source FBX may not contain animation."
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

    frame_start, frame_end = set_scene_to_animation_range(
        scene,
        active_action,
        nla_strips,
    )

    if frame_end < frame_start:
        raise RuntimeError(
            f"Invalid scene frame range: {frame_start} - {frame_end}"
        )

    print(f"Export frame range: {frame_start} - {frame_end}")

    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    spine_bone = next(
        (
            bone
            for bone in armature.data.bones
            if "spine" in bone.name.casefold()
        ),
        None,
    )
    if spine_bone is None:
        raise RuntimeError('No bone containing "spine" was found.')

    original_root_names = [
        bone.name
        for bone in armature.data.bones
        if bone.parent is None
    ]
    original_object_matrices: dict[int, Matrix] = {}
    original_child_world_matrices: dict[int, dict[str, Matrix]] = {}

    for frame in range(frame_start, frame_end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        object_matrix = armature.matrix_world.copy()
        original_object_matrices[frame] = object_matrix
        original_child_world_matrices[frame] = {
            name: object_matrix @ armature.pose.bones[name].matrix.copy()
            for name in original_root_names
        }

    base_object_matrix = original_object_matrices[frame_start].copy()

    new_root_name, child_names = add_root_bone(armature)
    animate_root_from_object_motion(
        scene,
        armature,
        new_root_name,
        child_names,
        original_object_matrices,
        original_child_world_matrices,
        base_object_matrix,
        frame_start,
        frame_end,
    )
    normalize_bone_names(armature)

    print("Normalized all bone names.")
    print(f"Sole final root bone: {new_root_name.lower()}")

    scene.frame_set(frame_start)
    bpy.context.view_layer.update()

    bpy.ops.object.select_all(action="DESELECT")
    armature.hide_set(False)
    armature.hide_viewport = False
    armature.hide_render = False
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    result = bpy.ops.export_scene.fbx(
        filepath=str(output_fbx),
        use_selection=True,
        object_types={"ARMATURE"},
        add_leaf_bones=True,
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

    if not output_fbx.is_file():
        raise RuntimeError(
            f"FBX exporter reported success, but no file was created: "
            f"{output_fbx}"
        )

    print(f"Exported animated FBX: {output_fbx}")


if __name__ == "__main__":
    main()