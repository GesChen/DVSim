# np_positions_to_fbx.py

import argparse
import json
from pathlib import Path

import bpy
import numpy as np
from mathutils import Matrix, Vector
from tqdm import tqdm


DEFAULT_BONE_TARGETS = {
    "Root": (0, 0),
    "BSpine": (0, 7),
    "USpine": (7, 8),
    "BHead": (8, 9),
    "UHead": (9, 10),
    "LClavicle": (8, 11),
    "LHumerus": (11, 12),
    "LUlna": (12, 13),
    "RClavicle": (8, 14),
    "RHumerus": (14, 15),
    "RUlna": (15, 16),
    "LPelvis": (0, 4),
    "LFemur": (4, 5),
    "LTibia": (5, 6),
    "RPelvis": (0, 1),
    "RFemur": (1, 2),
    "RTibia": (2, 3),
}


def parse_args():
    argv = []
    if "--" in __import__("sys").argv:
        argv = __import__("sys").argv[__import__("sys").argv.index("--") + 1:]

    p = argparse.ArgumentParser()

    p.add_argument("--np", required=True, help="Input .npy file. Shape: (frames, points, 3)")
    p.add_argument("--armature-blend", required=True, help="Source .blend containing armature")
    p.add_argument("--armature-name", required=True, help="Armature object name inside source .blend")
    p.add_argument("--out", required=True, help="Output .fbx path")

    p.add_argument("--fps", type=int, default=30)
    p.add_argument("--scale", type=float, default=1.0)
    p.add_argument("--collection", default="NP_Retarget")

    p.add_argument("--mapping-json", default=None, help="Optional JSON file: {bone_name: [head_i, tail_i]}")
    p.add_argument("--create-empties", action="store_true")
    p.add_argument("--empty-size", type=float, default=0.05)
    p.add_argument("--empty-type", default="PLAIN_AXES")

    p.add_argument("--no-clear-scene", action="store_true")
    p.add_argument("--keep-armature-animation", action="store_true")

    return p.parse_args(argv)


def get_action_fcurves(action):
    if not action:
        return []

    if hasattr(action, "fcurves"):
        return action.fcurves

    fcurves = []
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                fcurves.extend(channelbag.fcurves)
    return fcurves


def set_linear_interpolation(obj):
    ad = obj.animation_data
    if not ad or not ad.action:
        return

    for fc in get_action_fcurves(ad.action):
        for key in fc.keyframe_points:
            key.interpolation = "LINEAR"


def force_update():
    bpy.context.view_layer.update()
    bpy.context.evaluated_depsgraph_get().update()


def bone_depth(bone):
    d = 0
    p = bone.parent
    while p:
        d += 1
        p = p.parent
    return d


def reset_pose(armature):
    for pb in armature.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.location = (0, 0, 0)
        pb.rotation_quaternion = (1, 0, 0, 0)
        pb.scale = (1, 1, 1)


def append_armature(blend_path, object_name, collection):
    blend_path = Path(blend_path)

    if not blend_path.exists():
        raise FileNotFoundError(blend_path)

    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        if object_name not in data_from.objects:
            raise ValueError(f'Object "{object_name}" not found in {blend_path}')
        data_to.objects = [object_name]

    armature = data_to.objects[0]

    if armature.type != "ARMATURE":
        raise TypeError(f'"{object_name}" is not an armature object.')

    collection.objects.link(armature)
    return armature

def pose_bone_to_target(pb, target_tail, is_root):
    force_update()

    if is_root:
        # pb.head / pb.tail are in armature/object pose space.
        # Move the root pose matrix so its evaluated head lands on target_head.
        head = pb.head.copy()
        delta = target_tail - head

        m = pb.matrix.copy()
        m.translation += delta
        pb.matrix = m
        # pb.scale = (0.0, 0.0, 0.0)
        force_update()
        return

    head = pb.head.copy()
    tail = pb.tail.copy()

    cur_vec = tail - head
    dst_vec = target_tail - head

    if cur_vec.length < 1e-8 or dst_vec.length < 1e-8:
        return

    q = cur_vec.rotation_difference(dst_vec)
    s = dst_vec.length / cur_vec.length

    m = pb.matrix.copy()

    rot_about_head = (
        Matrix.Translation(head)
        @ q.to_matrix().to_4x4()
        @ Matrix.Translation(-head)
    )

    scale_about_head = (
        Matrix.Translation(head)
        @ Matrix.Diagonal((s, s, s, 1.0))
        @ Matrix.Translation(-head)
    )

    pb.matrix = scale_about_head @ rot_about_head @ m
    force_update()
    
def load_mapping(path):
    if path is None:
        return DEFAULT_BONE_TARGETS

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    return {str(k): (int(v[0]), int(v[1])) for k, v in raw.items()}


def main():
    args = parse_args()
    print('loading..')

    np_path = Path(args.np)
    blend_path = Path(args.armature_blend)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    bone_targets = load_mapping(args.mapping_json)

    if not np_path.exists():
        raise FileNotFoundError(np_path)

    data = np.load(np_path, allow_pickle=False).astype(np.float32)

    if data.ndim != 3 or data.shape[2] != 3:
        raise ValueError(f"Expected shape (frames, points, 3), got {data.shape}")

    # Source xyz -> Blender x z -y
    data = np.stack(
        (data[:, :, 0], data[:, :, 2], -data[:, :, 1]),
        axis=-1,
    )

    data *= args.scale

    frame_count, point_count, _ = data.shape

    if not args.no_clear_scene:
        bpy.ops.object.select_all(action="SELECT")
        bpy.ops.object.delete()

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = frame_count
    scene.render.fps = args.fps

    old = bpy.data.collections.get(args.collection)
    if old:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(old)

    collection = bpy.data.collections.new(args.collection)
    scene.collection.children.link(collection)

    if args.create_empties:
        empties = []

        for i, pos in enumerate(data[0]):
            empty = bpy.data.objects.new(f"pt_{i:04d}", None)
            empty.empty_display_type = args.empty_type
            empty.empty_display_size = args.empty_size
            empty.location = tuple(pos)
            collection.objects.link(empty)
            empties.append(empty)

        for frame_idx in range(frame_count):
            frame = frame_idx + 1
            for i, empty in enumerate(empties):
                empty.location = tuple(data[frame_idx, i])
                empty.keyframe_insert(data_path="location", frame=frame)

        for empty in empties:
            set_linear_interpolation(empty)

    armature = append_armature(blend_path, args.armature_name, collection)
    armature.data.pose_position = "POSE"

    if not args.keep_armature_animation:
        armature.animation_data_clear()

    missing = [name for name in bone_targets if name not in armature.pose.bones]
    if missing:
        raise ValueError(f"Mapped bones not found in armature: {missing}")

    bad_indices = []
    for bone_name, (head_i, tail_i) in bone_targets.items():
        if not (0 <= head_i < point_count):
            bad_indices.append((bone_name, "head", head_i))
        if not (0 <= tail_i < point_count):
            bad_indices.append((bone_name, "tail", tail_i))

    if bad_indices:
        raise IndexError(f"Bone target index out of range: {bad_indices}")

    ordered_pose_bones = sorted(
        [armature.pose.bones[name] for name in bone_targets],
        key=lambda pb: bone_depth(pb.bone),
    )

    arm_inv = armature.matrix_world.inverted()

    print('processing..')
    for frame_idx in tqdm(range(frame_count)):
        frame = frame_idx + 1
        scene.frame_set(frame)

        reset_pose(armature)
        force_update()

        frame_positions = data[frame_idx]

        for pb in ordered_pose_bones:
            _, tail_i = bone_targets[pb.name]

            target_tail_world = Vector(frame_positions[tail_i])
            target_tail_local = arm_inv @ target_tail_world

            pose_bone_to_target(pb, target_tail_local, 'root' in pb.name.lower())

            pb.keyframe_insert(data_path="location", frame=frame)
            pb.keyframe_insert(data_path="rotation_quaternion", frame=frame)
            pb.keyframe_insert(data_path="scale", frame=frame)

    set_linear_interpolation(armature)

    bpy.ops.object.select_all(action="DESELECT")
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature

    bpy.ops.export_scene.fbx(
        filepath=str(out_path),
        use_selection=True,
        object_types={"ARMATURE"},
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        bake_anim_force_startend_keying=True,
        add_leaf_bones=False,
        armature_nodetype="NULL",
    )

    print(f"Saved FBX: {out_path}")
    print(f"Frames: {frame_count}")
    print(f"Points: {point_count}")
    print(f"Bones retargeted: {len(bone_targets)}")


if __name__ == "__main__":
    main()