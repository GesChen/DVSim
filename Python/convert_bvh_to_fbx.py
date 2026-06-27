import sys
import os
import bpy

# EDIT THIS: all converted FBX files will be written here.
OUTPUT_DIR = r"C:\CProjects\Event Camera\DVSim\Assets\Assets\BVH"

# Optional import/export settings.
BVH_AXIS_FORWARD = '-Z'
BVH_AXIS_UP = 'Y'
FBX_AXIS_FORWARD = '-Z'
FBX_AXIS_UP = 'Y'


def clean_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete()


def convert_bvh_to_fbx(bvh_path: str) -> str:
    bvh_path = os.path.abspath(bvh_path)

    if not os.path.isfile(bvh_path):
        raise FileNotFoundError(f"BVH file not found: {bvh_path}")

    if not bvh_path.lower().endswith('.bvh'):
        raise ValueError(f"Input is not a .bvh file: {bvh_path}")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    base_name = os.path.splitext(os.path.basename(bvh_path))[0]
    fbx_path = os.path.join(OUTPUT_DIR, base_name + '.fbx')

    clean_scene()

    bpy.ops.import_anim.bvh(
        filepath=bvh_path,
        axis_forward=BVH_AXIS_FORWARD,
        axis_up=BVH_AXIS_UP,
        rotate_mode='NATIVE',
        update_scene_fps=True,
        update_scene_duration=True,
        use_fps_scale=False,
    )

    for obj in bpy.data.objects:
        if obj.type == 'ARMATURE':
            obj.name = "Armature"
            obj.data.name = "Armature"
            break

    # Select imported objects for export.
    bpy.ops.object.select_all(action='SELECT')

    bpy.ops.export_scene.fbx(
        filepath=fbx_path,
        use_selection=True,
        axis_forward=FBX_AXIS_FORWARD,
        axis_up=FBX_AXIS_UP,
        bake_anim=True,
        bake_anim_use_all_bones=True,
        bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=False,
        add_leaf_bones=False,
        object_types={'ARMATURE'},
    )

    return fbx_path


def main():
    # Blender args after "--" are treated as script args.
    if '--' not in sys.argv:
        print('ERROR: No BVH file argument received. Drag a .bvh onto convert_bvh_to_fbx.bat')
        sys.exit(2)

    input_files = sys.argv[sys.argv.index('--') + 1:]

    if not input_files:
        print('ERROR: No BVH file argument received.')
        sys.exit(2)

    failures = 0
    for bvh_path in input_files:
        try:
            fbx_path = convert_bvh_to_fbx(bvh_path)
            print(f'OK: {bvh_path} -> {fbx_path}')
        except Exception as exc:
            failures += 1
            print(f'FAILED: {bvh_path}')
            print(f'  {type(exc).__name__}: {exc}')

    sys.exit(1 if failures else 0)


if __name__ == '__main__':
    main()
